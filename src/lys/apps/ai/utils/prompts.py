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

# Purpose repairing a drifted spoken block: the turn carried the voice, the model
# wrote no block, and a focused chat call regenerates the spoken rendition from the
# written answer. A purpose of its own so its prompt is configured, overridden and
# versioned in ``ai_prompt_version`` like every other endpoint's.
AI_PURPOSE_SPOKEN_REPAIR = "spoken_repair"

# The repair instructions. Overridable like any endpoint prompt, by configuring a
# ``system_prompt`` on the ``spoken_repair`` endpoint — an app whose voice carries a
# persona will want its repair to speak in that persona too.
DEFAULT_SPOKEN_REPAIR_PROMPT = """You turn a written chatbot answer into its spoken rendition, read aloud by a speech synthesizer.

Rewrite the answer below FOR THE EAR:
- Self-sufficient: everything the answer establishes that the reader needs —
  names, figures, definitions, warnings — is said aloud. A listener must never
  have to re-ask what the written text already said.
- Plain text: no markdown, no bold, no headings, no tables. Short lists are
  allowed when they genuinely help the ear.
- Write every number, amount and symbol the way it is spoken, in full words;
  spell units and symbols out in the answer's language.
- Conversational, as long as the content needs and no longer.

Output ONLY the spoken text. No tags, no preamble, no quotation marks."""

# Purpose -> the framework's own instructions for it. A mapping rather than a chain
# of comparisons: the next purpose to join is one entry, not another branch.
FRAMEWORK_DEFAULT_SYSTEM_PROMPTS: Dict[str, str] = {
    AI_PURPOSE_SPOKEN_REPAIR: DEFAULT_SPOKEN_REPAIR_PROMPT,
}


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
