"""
Framework-owned default system prompts, keyed by purpose.

Most purposes carry application content: their prompt is the consuming project's
voice and the framework has nothing to say about it. A few are mechanisms lys
drives itself — it makes the call, it knows the task, and the consumer only
decides whether the feature is on. For those, a default the consumer has to copy
into its settings to obtain is not a default: forget it and the call runs with NO
system prompt at all, which nothing reports — the model is handed a task without
its instructions and answers something plausible instead.

This module is the single home for those defaults. It sits in ``utils`` rather
than beside the mechanism that uses each prompt because the config layer
(``utils.providers.config``) applies them while parsing the plugin config, and
that layer cannot import upward from ``modules``.

A purpose absent from here has no framework instructions, by design.
"""

from typing import Dict, Optional

# Purpose -> the framework's own instructions for it. A mapping rather than a chain
# of comparisons: the next purpose to join is one entry, not another branch. Empty
# today: the framework currently drives no purpose of its own — the mapping stays
# because the mechanism (config-layer default application, ai_prompt_version)
# is what the next mechanism will plug into.
FRAMEWORK_DEFAULT_SYSTEM_PROMPTS: Dict[str, str] = {}


def framework_default_system_prompt(purpose: str) -> Optional[str]:
    """
    The framework's own instructions for a purpose whose mechanism it owns.

    Args:
        purpose: The endpoint's purpose name.

    Returns:
        The framework's default prompt for that purpose, or None when the purpose
        carries application content only.
    """
    return FRAMEWORK_DEFAULT_SYSTEM_PROMPTS.get(purpose)
