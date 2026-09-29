"""
Input-size constants shared by the validators and by the components that must
bound the same strings before they reach them.

Here rather than in ``lys.core.utils.validators``: that module imports app errors
and app consts, so importing it for a number drags those apps into any component
that needs one. A constant has no dependencies and every layer may read it.
"""

# The longest search term the API accepts (``validate_search_input``). Also the
# default cap of a ``text`` page param (``lys.apps.ai.utils.page_params``): the
# two bound the same kind of string, and a page param bounded lower than the
# input filling it would be dropped after the user typed it.
MAX_SEARCH_LENGTH = 200
