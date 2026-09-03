"""
Text search helpers: resolving which PostgreSQL configuration indexes a message.

A tsvector cannot be read without the configuration that produced it - lexemes are
stemmed by a given configuration, and a query stemmed by another one will not match
them. So the configuration is decided per message, at indexing time, and stored beside
the vector.

It is detected from the content rather than taken from a global setting or from the
author's interface language: two users of the same instance legitimately write in two
languages, and the language someone reads the interface in says nothing about the
language they paste a report in.
"""

import logging
from typing import Optional

from langdetect import DetectorFactory, LangDetectException, detect

logger = logging.getLogger(__name__)

# langdetect is probabilistic and seeds itself at random, so the same text can be filed
# under two languages across runs. Seeding makes indexing reproducible - two identical
# messages get the same configuration, and a bug is investigable.
DetectorFactory.seed = 0

# PostgreSQL ships a text search configuration per language, named in English. Mapping is
# by ISO 639-1 code, which is what `lys.apps.base` uses for its Language entity.
ISO_TO_TEXT_SEARCH_CONFIG = {
    "ar": "arabic",
    "ca": "catalan",
    "da": "danish",
    "de": "german",
    "el": "greek",
    "en": "english",
    "es": "spanish",
    "eu": "basque",
    "fi": "finnish",
    "fr": "french",
    "ga": "irish",
    "hi": "hindi",
    "hu": "hungarian",
    "hy": "armenian",
    "id": "indonesian",
    "it": "italian",
    "lt": "lithuanian",
    "ne": "nepali",
    "nl": "dutch",
    "no": "norwegian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sr": "serbian",
    "sv": "swedish",
    "ta": "tamil",
    "tr": "turkish",
    "yi": "yiddish",
}

# Falls back to `simple`, which indexes words as they are written, with no stemming and no
# stop words. It is the honest answer for a text whose language could not be established:
# the message stays searchable by exact term rather than being indexed under a language it
# is not written in, which would stem it wrongly and hide it from every query.
DEFAULT_TEXT_SEARCH_CONFIG = "simple"

# Below this, detection is a coin toss - lingua reports ~74% on a single word against
# ~99.7% on a sentence. Short chat turns ("ok", "vas-y", "et la tréso ?") carry almost
# nothing to stem, so guessing their language buys nothing and risks filing them wrong.
MIN_CHARS_FOR_DETECTION = 40


def resolve_text_search_config(content: Optional[str]) -> str:
    """
    Return the PostgreSQL text search configuration to index a message with.

    Detected from the content, not from the author's interface language: two users of the
    same instance legitimately write in two languages, and someone reading the interface
    in French may well paste an English report.

    Falls back to `simple` whenever the language cannot be established with confidence -
    a text too short to detect, an unsupported language, or a detector failure. Never
    raises: indexing must not fail a message over its language.
    """
    if not content:
        return DEFAULT_TEXT_SEARCH_CONFIG

    text = content.strip()

    # Below the threshold, detection is close to a coin toss, and there is nothing to stem
    # in a four-word turn anyway - `simple` indexes it verbatim, which is what it needs.
    if len(text) < MIN_CHARS_FOR_DETECTION:
        return DEFAULT_TEXT_SEARCH_CONFIG

    try:
        iso_code = detect(text)
    except LangDetectException:
        return DEFAULT_TEXT_SEARCH_CONFIG

    # langdetect returns regional codes for some languages (zh-cn, pt-br); the mapping is
    # keyed on the base language, which is what a text search configuration covers.
    return ISO_TO_TEXT_SEARCH_CONFIG.get(
        iso_code.split("-")[0], DEFAULT_TEXT_SEARCH_CONFIG
    )


# Tool definition for search_conversation.
#
# Only offered once a conversation has been compacted: before that the whole exchange is
# already in the prompt, and a model given a search tool over what it can already read
# would burn a turn rediscovering it.
SEARCH_CONVERSATION_TOOL = {
    "type": "function",
    "function": {
        "name": "search_conversation",
        "description": (
            "Search what was SAID earlier in this conversation, in the part now condensed "
            "into the summary above. Use it when the user refers back to something the "
            "summary does not spell out - a decision they took, a constraint they stated, "
            "a preference they expressed - rather than asking them to repeat it.\n"
            "Do NOT use it to look up data. Figures, metrics and records come from the "
            "tools that read them, which return the current values; this one returns what "
            "was written at the time, which may since have changed.\n"
            "Do NOT use it for the recent exchange either: the messages still shown to you "
            "are already complete, and searching them finds nothing you cannot read."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Words to look for, in the language of the conversation. Quotes "
                        "match an exact phrase, OR widens, a leading minus excludes."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}
