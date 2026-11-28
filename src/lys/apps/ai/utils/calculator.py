"""
Exact arithmetic for the chatbot: the ``calculate`` special tool.

A language model computes in its head. It gets a single operation right and loses the thread of a
chain - a projection carried over several steps, an intermediate result reused two lines later. This
tool evaluates the chain instead, in decimal arithmetic, from the formulas the model writes.

The formulas are parsed, never executed: each expression is a Python AST checked against a whitelist
(numbers, the four operations and the power, the names of the previous steps, a few functions) and
evaluated by walking that tree. Nothing else in the language is reachable - no attribute, no call
outside the whitelist, no import, no name the steps did not define - and every input is bounded
(steps, length, size of the tree, exponent, magnitude), so a formula costs microseconds whatever the
model writes.
"""

import ast
import re
from decimal import (
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

from lys.apps.ai.utils.provenance import Figure, Provenance, mixed_bases

#: Steps one call may chain: enough for a projection, short enough to stay readable in the history
MAX_STEPS = 20

#: Characters one expression may hold
MAX_EXPRESSION_LENGTH = 300

#: Nodes one parsed expression may hold: bounds the walk, whatever the text
MAX_EXPRESSION_NODES = 200

#: Largest exponent a power may take: an n-th root or a compounding over periods, not more
MAX_EXPONENT = 1000

#: Significant digits of the arithmetic, and the decimal exponent range of every value (about
#: 1e-30 to 1e30): far beyond any amount, and a bound that turns a runaway power into an error
PRECISION = 28
MAX_MAGNITUDE = 30

#: Decimals a result is returned with: a ratio keeps its precision, the model rounds for display
RESULT_DECIMALS = 10

#: Digits round() may be asked for, on either side of the decimal point
MAX_ROUND_DIGITS = 12

#: A step name: lower case, so it cannot shadow a function and reads like a variable
STEP_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")

SYNTAX_HINT = (
    "write it in Python syntax: a decimal point, no thousands separator, * to multiply, ** for a power, "
    "a percentage as a fraction (5 % is 0.05)"
)


class CalculationError(ValueError):
    """A formula the tool refuses or cannot evaluate; the message is written for the model to fix it."""


def _round(value: Decimal, digits: Decimal = Decimal(0)) -> Decimal:
    """round(x, digits), half up - how an amount is rounded, not the banker's rounding of Python."""
    if digits != digits.to_integral_value() or abs(digits) > MAX_ROUND_DIGITS:
        raise CalculationError(f"round() takes a whole number of digits between -{MAX_ROUND_DIGITS} "
                               f"and {MAX_ROUND_DIGITS}")
    return value.quantize(Decimal(1).scaleb(-int(digits)), rounding=ROUND_HALF_UP)


def _min(*values: Decimal) -> Decimal:
    return min(values)


def _max(*values: Decimal) -> Decimal:
    return max(values)


def _sum(*values: Decimal) -> Decimal:
    return sum(values, Decimal(0))


#: name -> (function, fewest arguments, most arguments - None for any number)
FUNCTIONS: Dict[str, Tuple[Callable[..., Decimal], int, Any]] = {
    "round": (_round, 1, 2),
    "abs": (abs, 1, 1),
    "min": (_min, 1, None),
    "max": (_max, 1, None),
    "sum": (_sum, 1, None),
}

BINARY_OPERATORS: Dict[type, Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
}


def _arithmetic_context() -> Context:
    """The decimal context every step runs in: bounded, and trapping what has no answer."""
    return Context(
        prec=PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emax=MAX_MAGNITUDE,
        Emin=-MAX_MAGNITUDE,
        traps=[DivisionByZero, Overflow, InvalidOperation],
    )


class _Evaluator:
    """Walks one parsed expression against the whitelist, with the values of the previous steps."""

    def __init__(self, source: str, values: Dict[str, Decimal]):
        self.source = source
        self.values = values

    def evaluate(self, node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.Constant):
            return self._number(node)
        if isinstance(node, ast.Name):
            if node.id not in self.values:
                raise CalculationError(f"unknown name '{node.id}': define it in an earlier step")
            return self.values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = self.evaluate(node.operand)
            return -operand if isinstance(node.op, ast.USub) else +operand
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            return self._power(self.evaluate(node.left), self.evaluate(node.right))
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
            return BINARY_OPERATORS[type(node.op)](self.evaluate(node.left), self.evaluate(node.right))
        if isinstance(node, ast.Call):
            return self._call(node)
        raise CalculationError(f"'{ast.get_source_segment(self.source, node) or type(node).__name__}' is not "
                               f"allowed: only numbers, + - * / **, parentheses, the names of earlier steps "
                               f"and {', '.join(FUNCTIONS)}")

    def _number(self, node: ast.Constant) -> Decimal:
        """A literal, read from its text so 0.1 stays exactly 0.1 (never through a binary float)."""
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculationError(f"{node.value!r} is not a number")
        text = ast.get_source_segment(self.source, node) or ""
        try:
            return +Decimal(text)
        except InvalidOperation:
            raise CalculationError(f"'{text}' is not a decimal number: {SYNTAX_HINT}") from None

    @staticmethod
    def _power(base: Decimal, exponent: Decimal) -> Decimal:
        if abs(exponent) > MAX_EXPONENT:
            raise CalculationError(f"exponent {exponent} is beyond {MAX_EXPONENT}")
        return base ** exponent

    def _call(self, node: ast.Call) -> Decimal:
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name not in FUNCTIONS:
            raise CalculationError(f"unknown function: only {', '.join(FUNCTIONS)}")
        if node.keywords or any(isinstance(argument, ast.Starred) for argument in node.args):
            raise CalculationError(f"{name}() takes its numbers as plain arguments, e.g. {name}(a, b)")
        function, fewest, most = FUNCTIONS[name]
        if len(node.args) < fewest or (most is not None and len(node.args) > most):
            expected = str(fewest) if fewest == most else f"{fewest} to {most}" if most else f"at least {fewest}"
            raise CalculationError(f"{name}() takes {expected} argument(s), got {len(node.args)}")
        return function(*(self.evaluate(argument) for argument in node.args))


def _parse(expression: str) -> ast.Expression:
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculationError(f"expression longer than {MAX_EXPRESSION_LENGTH} characters: split it into steps")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError):
        raise CalculationError(f"not a valid formula: {SYNTAX_HINT}") from None
    if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
        raise CalculationError("expression too large: split it into steps")
    return tree


def _decimal_failure(error: DecimalException) -> str:
    if isinstance(error, DivisionByZero):
        return "division by zero"
    if isinstance(error, Overflow):
        return f"result beyond 1e{MAX_MAGNITUDE}"
    return "undefined result (e.g. a negative number raised to a fractional power, or 0 / 0)"


def evaluate_steps(steps: Any) -> List[Tuple[str, str, Decimal]]:
    """
    Evaluate a chain of named formulas, in order.

    Args:
        steps: [{"name": ..., "expression": ...}]; a step may use the names of the steps before it

    Returns:
        (name, expression, value) per step, in order

    Raises:
        CalculationError: a malformed step or a formula that cannot be evaluated, its message naming
            the step - the first failing step stops the chain, since the next ones may depend on it
    """
    if not isinstance(steps, list) or not steps:
        raise CalculationError("steps must be a non-empty list of {name, expression}")
    if len(steps) > MAX_STEPS:
        raise CalculationError(f"at most {MAX_STEPS} steps per call")

    values: Dict[str, Decimal] = {}
    results = []
    with localcontext(_arithmetic_context()):
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise CalculationError(f"step {index} must be an object {{name, expression}}")
            name, expression = step.get("name"), step.get("expression")
            if not isinstance(name, str) or not STEP_NAME_PATTERN.match(name):
                raise CalculationError(f"step {index}: name must be lower case letters, digits and _ "
                                       f"(e.g. monthly_burn), got {name!r}")
            if name in values or name in FUNCTIONS:
                raise CalculationError(f"step {index}: name '{name}' is already taken")
            if not isinstance(expression, str) or not expression.strip():
                raise CalculationError(f"step '{name}': expression must be a non-empty text")
            try:
                value = _Evaluator(expression.strip(), values).evaluate(_parse(expression))
            except CalculationError as error:
                raise CalculationError(f"step '{name}': {error}") from None
            except DecimalException as error:
                raise CalculationError(f"step '{name}': {_decimal_failure(error)}") from None
            values[name] = value
            results.append((name, expression.strip(), value))
    return results


def format_result(value: Decimal) -> str:
    """A value as plain decimal text, without exponent nor trailing zeros, to RESULT_DECIMALS at most."""
    with localcontext(_arithmetic_context()) as context:
        # Quantizing needs the integer digits plus the decimals to fit the precision.
        if value.adjusted() + RESULT_DECIMALS < PRECISION:
            value = value.quantize(Decimal(1).scaleb(-RESULT_DECIMALS), rounding=ROUND_HALF_UP)
        text = format(value.normalize(context), "f")
    return "0" if text in ("-0", "0") else text


def handle_calculate(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Special-tool handler of ``calculate``.

    A refused or failing formula is returned as an error the model can act on (lys AI guide, special
    tools R2), never raised through the turn.
    """
    return build_calculate_handler(None)(arguments, context)


def build_calculate_handler(
    provenance: Optional[Provenance],
) -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """
    The ``calculate`` handler of a conversation whose tools state where their figures come from
    (``lys.apps.ai.utils.provenance``): the results come with a warning for each step that sets two
    figures on different bases against each other (``mixed_base_warnings``). The result is computed
    all the same: the model decides, the warning says what it combined.
    """
    def handler(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = evaluate_steps(arguments.get("steps"))
        except CalculationError as error:
            return {"error": str(error)}
        answer: Dict[str, Any] = {
            "results": [
                {"name": name, "expression": expression, "value": format_result(value)}
                for name, expression, value in results
            ]
        }
        warnings = mixed_base_warnings(results, provenance) if provenance is not None else []
        if warnings:
            answer["warnings"] = warnings
        return answer
    return handler


def mixed_base_warnings(results: List[Tuple[str, str, Decimal]], provenance: Provenance) -> List[str]:
    """
    What the steps of a chain set against each other although it is not on the same basis: an
    addition, a subtraction or a division between two figures the tools showed in the same unit, of
    different measures, read in different sources (``provenance.mixed_bases``). A number of a formula
    is a tool's figure when the provenance tells which one it is; a step carries the figures it was
    computed from to the steps that use its name. One warning per step at most.
    """
    origins: Dict[str, FrozenSet[Figure]] = {}
    warnings = []
    for name, expression, _ in results:
        found: List[Tuple[str, Figure, Figure]] = []
        origins[name] = _origins(_parse(expression).body, expression, origins, provenance, found)
        if found:
            operator, one, other = found[0]
            warnings.append(
                f"step '{name}': {_described(one)} and {_described(other)} are two different measures read "
                f"in two different sources, set against each other by '{operator}'. They are not on the same "
                f"basis: read the definitions the tools gave before using this result. When a tool gives the "
                f"figure you are computing, quote it instead; if you keep this result, say how it was computed."
            )
    return warnings


#: The operations that set two figures against each other: a multiplication applies a rate or a
#: count to an amount, it compares nothing
_COMPARING_OPERATORS = {ast.Add: "+", ast.Sub: "-", ast.Div: "/"}


def _origins(
    node: ast.AST, source: str, origins: Dict[str, FrozenSet[Figure]], provenance: Provenance,
    found: List[Tuple[str, Figure, Figure]],
) -> FrozenSet[Figure]:
    """The figures a node of a formula is computed from, recording each mixed comparison it holds."""
    if isinstance(node, ast.Constant):
        try:
            literal = Decimal(ast.get_source_segment(source, node) or "")
        except InvalidOperation:
            return frozenset()
        known = provenance.figure_of(literal, max(0, -literal.as_tuple().exponent))
        return frozenset([known]) if known is not None else frozenset()
    if isinstance(node, ast.Name):
        return origins.get(node.id, frozenset())
    if isinstance(node, ast.UnaryOp):
        return _origins(node.operand, source, origins, provenance, found)
    if isinstance(node, ast.BinOp):
        left = _origins(node.left, source, origins, provenance, found)
        right = _origins(node.right, source, origins, provenance, found)
        operator = _COMPARING_OPERATORS.get(type(node.op))
        mixed = mixed_bases(left, right) if operator else None
        if mixed is not None:
            found.append((operator, *mixed))
        return left | right
    if isinstance(node, ast.Call):
        figures: FrozenSet[Figure] = frozenset()
        for argument in node.args:
            figures |= _origins(argument, source, origins, provenance, found)
        return figures
    return frozenset()


def _described(item: Figure) -> str:
    return f"{format_result(item.value)} ({item.label}, source {item.source})"


# Tool definition for calculate. Offered on every turn: it reads nothing and changes nothing, so
# there is no page it would not make sense on.
CALCULATE_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Exact decimal arithmetic. Use it for EVERY figure you derive yourself - a sum, a difference, "
            "a ratio, a percentage, a growth rate, a projection - instead of computing in your head, and "
            "above all when one result feeds the next: the steps run in order, and a step uses the names "
            "of the steps before it (e.g. months_left = 3, then cash_end = 40000 - 15000 * months_left). "
            "Take each figure as the tool that returned it gave it, all in one unit. Python syntax: a "
            "decimal point, no thousands separator, * to multiply, ** for a power (an n-th root is "
            "** (1 / n)), a percentage as a fraction (5 % is 0.05). Functions: round(x, digits) (half up), "
            "min, max, abs, sum - each takes its numbers as arguments. Returns each step's value, or an "
            "error naming the step to fix. Do NOT use it to recompute a figure a tool already returned "
            "computed (a change, a total, a rate): quote that figure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": f"The formulas, evaluated in order (1 to {MAX_STEPS}).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "What the step computes, in lower case with _ "
                                               "(e.g. monthly_burn); later steps use it as a variable.",
                            },
                            "expression": {
                                "type": "string",
                                "description": "The formula, with numbers and the names of earlier steps.",
                            },
                        },
                        "required": ["name", "expression"],
                    },
                }
            },
            "required": ["steps"],
        },
    },
}
