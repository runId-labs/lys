"""
Unit tests for lys.apps.ai.utils.calculator.

The evaluator must compute exactly what the formulas say, and refuse everything else the Python
grammar allows - attributes, calls outside the whitelist, unbounded inputs - with an error the
model can act on.
"""

import time
from decimal import Decimal

import pytest

from lys.apps.ai.utils.calculator import (
    CALCULATE_TOOL,
    MAX_EXPRESSION_LENGTH,
    MAX_STEPS,
    CalculationError,
    evaluate_steps,
    format_result,
    handle_calculate,
)


def value_of(expression: str) -> Decimal:
    return evaluate_steps([{"name": "x", "expression": expression}])[0][2]


def error_of(steps) -> str:
    result = handle_calculate({"steps": steps}, {})
    assert "results" not in result
    return result["error"]


class TestArithmetic:

    def test_decimal_literals_stay_exact(self):
        assert value_of("0.1 + 0.2") == Decimal("0.3")

    def test_operator_precedence_and_parentheses(self):
        assert value_of("2 + 3 * 4") == 14
        assert value_of("(2 + 3) * 4") == 20
        assert value_of("-2 ** 2") == -4

    def test_division_keeps_decimals(self):
        assert format_result(value_of("1 / 3")) == "0.3333333333"

    def test_fractional_power_for_a_growth_rate(self):
        rate = value_of("(5112908.03 / 3847291.47) ** (1 / 3) - 1")
        assert format_result(round(rate * 100, 3)) == "9.944"

    def test_annuity_payment(self):
        payment = value_of("487350 * (0.0437 / 12) / (1 - (1 + 0.0437 / 12) ** -84)")
        assert format_result(round(payment, 2)) == "6744.82"

    def test_round_is_half_up_not_bankers(self):
        assert value_of("round(0.125, 2)") == Decimal("0.13")
        assert value_of("round(2.5)") == 3

    def test_round_to_thousands(self):
        assert format_result(value_of("round(1234567, -3)")) == "1235000"

    def test_variadic_functions(self):
        assert value_of("sum(1, 2, 3.5)") == Decimal("6.5")
        assert value_of("min(3, -1, 2)") == -1
        assert value_of("max(3, -1, 2)") == 3
        assert value_of("abs(-4.2)") == Decimal("4.2")

    def test_underscore_digit_grouping_is_read(self):
        assert value_of("1_000 * 2") == 2000


class TestSteps:

    def test_a_step_uses_the_previous_ones(self):
        results = evaluate_steps([
            {"name": "cash", "expression": "40000"},
            {"name": "monthly_burn", "expression": "100000 / 6"},
            {"name": "cash_end", "expression": "cash - monthly_burn * 3"},
        ])
        assert [name for name, _, _ in results] == ["cash", "monthly_burn", "cash_end"]
        assert format_result(results[2][2]) == "-10000"

    def test_a_later_name_is_not_visible_earlier(self):
        assert "unknown name 'b'" in error_of([
            {"name": "a", "expression": "b + 1"},
            {"name": "b", "expression": "1"},
        ])

    def test_the_failing_step_is_named(self):
        message = error_of([
            {"name": "ok", "expression": "1"},
            {"name": "broken", "expression": "ok / 0"},
        ])
        assert message == "step 'broken': division by zero"

    @pytest.mark.parametrize("name", ["Revenue", "1st", "a-b", "", "x" * 41, None, 3])
    def test_invalid_names_are_refused(self, name):
        assert "name must be" in error_of([{"name": name, "expression": "1"}])

    def test_duplicate_name_is_refused(self):
        assert "already taken" in error_of([
            {"name": "a", "expression": "1"},
            {"name": "a", "expression": "2"},
        ])

    def test_a_function_name_cannot_be_a_step(self):
        assert "already taken" in error_of([{"name": "round", "expression": "1"}])

    @pytest.mark.parametrize("steps", [None, [], "1 + 1", [{"name": "a"}], [{"name": "a", "expression": " "}], [1]])
    def test_malformed_steps_are_refused(self, steps):
        error_of(steps)

    def test_too_many_steps_are_refused(self):
        steps = [{"name": f"s{index}", "expression": "1"} for index in range(MAX_STEPS + 1)]
        assert f"at most {MAX_STEPS}" in error_of(steps)


class TestRefusals:

    @pytest.mark.parametrize("expression", [
        "__import__('os').system('ls')",
        "(1).__class__",
        "x.real",
        "open('/etc/passwd')",
        "eval('1')",
        "[1, 2]",
        "{1: 2}",
        "(1, 2)",
        "lambda: 1",
        "1 if 1 else 2",
        "1 < 2",
        "not 1",
        "7 // 2",
        "7 % 2",
        "1 << 2",
        "'a'",
        "True + 1",
        "None",
        "2j",
        "[x for x in (1, 2)]",
    ])
    def test_anything_outside_the_grammar_is_refused(self, expression):
        with pytest.raises(CalculationError):
            value_of(expression)

    def test_keyword_and_starred_arguments_are_refused(self):
        with pytest.raises(CalculationError, match="plain arguments"):
            value_of("round(1.25, ndigits=1)")
        with pytest.raises(CalculationError, match="plain arguments"):
            value_of("sum(*(1, 2))")

    def test_function_arity_is_checked(self):
        with pytest.raises(CalculationError, match="takes 1 argument"):
            value_of("abs(1, 2)")
        with pytest.raises(CalculationError, match="takes 1 to 2"):
            value_of("round(1, 2, 3)")

    def test_round_digits_are_bounded(self):
        with pytest.raises(CalculationError, match="whole number of digits"):
            value_of("round(1, 0.5)")
        with pytest.raises(CalculationError, match="whole number of digits"):
            value_of("round(1, 13)")

    def test_thousands_separators_are_explained(self):
        with pytest.raises(CalculationError, match="no thousands separator"):
            value_of("1 234,5")

    def test_negative_base_to_a_fractional_power_is_undefined(self):
        assert "undefined result" in error_of([{"name": "x", "expression": "(-8) ** 0.5"}])


class TestBounds:

    def test_runaway_power_fails_fast(self):
        start = time.perf_counter()
        assert "exponent" in error_of([{"name": "x", "expression": "9 ** 9 ** 9"}])
        assert time.perf_counter() - start < 0.5

    def test_magnitude_is_bounded(self):
        assert "result beyond" in error_of([{"name": "x", "expression": "10 ** 999"}])
        assert "result beyond" in error_of([{"name": "x", "expression": "1e400"}])

    def test_long_expression_is_refused(self):
        expression = "+".join(["1"] * (MAX_EXPRESSION_LENGTH // 2 + 1))
        assert "longer than" in error_of([{"name": "x", "expression": expression}])

    def test_large_tree_is_refused(self):
        assert "too large" in error_of([{"name": "x", "expression": "+".join(["1"] * 120)}])

    def test_nesting_is_bounded_by_the_tree_size(self):
        # Parentheses add no node: a deeply parenthesised number is just a number.
        assert value_of("(" * 140 + "1" + ")" * 140) == 1
        # Each nested operation is a node: the walk's depth is bounded with the tree.
        assert "too large" in error_of([{"name": "x", "expression": "-" * 250 + "1"}])


class TestFormatting:

    @pytest.mark.parametrize("value, expected", [
        (Decimal("100.000"), "100"),
        (Decimal("1E+3"), "1000"),
        (Decimal("-0.0"), "0"),
        (Decimal("2.50"), "2.5"),
        (Decimal("123456789012345678.5"), "123456789012345678.5"),
    ])
    def test_plain_decimal_text(self, value, expected):
        assert format_result(value) == expected


class TestHandler:

    def test_returns_each_step_with_its_expression(self):
        result = handle_calculate({"steps": [
            {"name": "months", "expression": " 3 "},
            {"name": "total", "expression": "months * 1.5"},
        ]}, {})
        assert result == {"results": [
            {"name": "months", "expression": "3", "value": "3"},
            {"name": "total", "expression": "months * 1.5", "value": "4.5"},
        ]}

    def test_missing_steps_is_an_error_not_a_raise(self):
        assert "error" in handle_calculate({}, {})

    def test_tool_definition_matches_the_handler(self):
        function = CALCULATE_TOOL["function"]
        assert function["name"] == "calculate"
        assert function["parameters"]["required"] == ["steps"]
        assert function["parameters"]["properties"]["steps"]["items"]["required"] == ["name", "expression"]


class TestMixedBases:
    """A formula setting two figures of different bases against each other is computed, and said."""

    @staticmethod
    def _provenance():
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, Provenance, figure

        provenance = Provenance()
        provenance.add({"content": "table", PROVENANCE_KEY: [
            figure(1250000, "loaded_cost", "loaded cost 2030", "ledger", "EUR"),
            figure(1000000, "gross_payroll", "gross payroll 2030", "payroll", "EUR"),
            figure(40, "headcount", "headcount 2030", "payroll", "persons"),
            figure(1040000, "salaries", "salaries 2030", "ledger", "EUR"),
            figure(210000, "employer_contributions", "employer contributions 2030", "ledger", "EUR"),
        ]})
        return provenance

    def _run(self, *expressions):
        from lys.apps.ai.utils.calculator import build_calculate_handler

        steps = [{"name": f"s{index}", "expression": text} for index, text in enumerate(expressions)]
        return build_calculate_handler(self._provenance())({"steps": steps}, {})

    def test_two_measures_of_two_sources_subtracted_are_warned_and_still_computed(self):
        result = self._run("(1250000 - 1000000) / 1000000")
        assert result["results"][0]["value"] == "0.25"
        assert len(result["warnings"]) == 1
        assert "loaded cost 2030, source ledger" in result["warnings"][0]
        assert "gross payroll 2030, source payroll" in result["warnings"][0]

    def test_figures_written_in_thousands_are_recognised(self):
        assert "warnings" in self._run("1250 - 1000")

    def test_a_step_carries_its_figures_to_the_steps_using_it(self):
        result = self._run("1250000 * 1", "s0 - 1000000")
        assert [warning.split(":")[0] for warning in result["warnings"]] == ["step 's1'"]

    def test_one_source_own_arithmetic_is_not_warned(self):
        assert "warnings" not in self._run("210000 / 1040000")

    def test_an_amount_per_head_is_not_warned(self):
        assert "warnings" not in self._run("1250000 / 40")

    def test_a_rate_applied_to_an_amount_is_not_warned(self):
        assert "warnings" not in self._run("1000000 * 0.21")

    def test_a_number_no_tool_showed_is_not_warned(self):
        assert "warnings" not in self._run("1250000 - 1234567")

    def test_without_provenance_the_handler_answers_as_before(self):
        result = handle_calculate({"steps": [{"name": "s", "expression": "1250000 - 1000000"}]}, {})
        assert "warnings" not in result


class TestProvenance:

    def test_the_model_never_gets_the_provenance(self):
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, model_result

        stored = {"content": "table", PROVENANCE_KEY: []}
        assert model_result(stored) == {"content": "table"} and PROVENANCE_KEY in stored
        assert model_result("text") == "text"

    def test_a_value_shown_for_two_kinds_of_figure_says_nothing(self):
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, Provenance, figure

        provenance = Provenance()
        provenance.add({PROVENANCE_KEY: [figure(1500, "a", "a", "x", "EUR"), figure(1500, "b", "b", "y", "EUR")]})
        assert provenance.figure_of(Decimal("1500"), 0) is None

    def test_a_short_number_says_nothing(self):
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, Provenance, figure

        provenance = Provenance()
        provenance.add({PROVENANCE_KEY: [figure(12, "months", "months", "x", "months")]})
        assert provenance.figure_of(Decimal("12"), 0) is None

    def test_malformed_entries_are_left_out(self):
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, Provenance

        provenance = Provenance()
        provenance.add({PROVENANCE_KEY: [None, {"value": "x"}, {"value": "100", "measure": "m"}]})
        provenance.add({PROVENANCE_KEY: "not a list"})
        assert provenance.figure_of(Decimal("100"), 0) is None
