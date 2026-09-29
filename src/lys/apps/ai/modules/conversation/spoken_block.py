"""
Spoken answer support for the chatbot — the direct voice.

The model writes ONE answer — naturally speakable prose, the app's own prompt
carries the voice-first style — and the synthesizer reads it through
:func:`normalize_speech`: a mechanical, deterministic pass (markdown out,
amounts and symbols spelled in words). No tags, no second rendition, no
repair call: what is written is what is said.

Everything here is generic framework mechanism, no application content:
whether the feature exists at all is the ``chatbot.spoken_block.enabled``
setting, and which words a language says is one ``SpeechVocabulary`` table
selected by ``chatbot.spoken_block.language`` — an app that declares none gets
the markdown strip alone, never another language's words.

Pure blocks only, no provider and no socket: unit-testable without a TTS key.
"""

import asyncio
import base64
import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Dict, List, Optional, Tuple

from lys.apps.ai.utils.sse import format_sse

logger = logging.getLogger(__name__)

# What one line of configuration looks like. Absent or ``enabled: false`` means
# the feature does not exist: the answer is what the model wrote, whole, and no
# synthesizer reads it.
@dataclass(frozen=True)
class SpokenBlockConfig:
    """The feature's configuration, resolved from the AI plugin settings."""

    enabled: bool = False
    language: Optional[str] = None

    @classmethod
    def from_plugin_config(cls, chatbot_config: Dict) -> "SpokenBlockConfig":
        """Read ``chatbot.spoken_block`` from the AI plugin configuration.

        A partial dict is fine — only ``enabled`` decides existence, an app
        that only says ``{"enabled": True}`` gets a working voice reading the
        answer with its markdown stripped.

        ``language`` names the spoken vocabulary to apply on top of that strip
        (figures said in words, symbols and units spelled). It is opt-in on
        purpose: the framework speaks no language by default, and an app that
        does not declare one gets the strip alone rather than another
        language's words.
        """
        raw = chatbot_config.get("spoken_block") or {}
        language = raw.get("language")
        return cls(
            enabled=bool(raw.get("enabled", False)),
            language=str(language).lower() if language else None,
        )


def strip_markdown_for_speech(text: str) -> str:
    """
    Reduce a written answer to something a voice can read honestly.

    Headings lose their markers, emphasis and inline code lose their marks, a
    link keeps its text and drops its URL — a URL read aloud is noise, never
    information — table rows become "cell · cell · cell" (a table read aloud is
    a list, not a grid) and list bullets become spoken enumeration.

    A bare URL left in the prose is NOT removed: dropping it would silently lose
    what the answer said, and this function only strips marks, never content.
    """
    stripped = text
    # Links before emphasis: the text inside a link may itself be emphasized,
    # and the URL must go before anything else tries to read its punctuation.
    # The image's alt text is what a listener can be told; its URL is not.
    stripped = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", stripped)
    stripped = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", stripped)
    # An autolink is a URL wrapped in angle brackets — the brackets are marks.
    stripped = re.sub(r"<(https?://[^>\s]+)>", r"\1", stripped)
    stripped = re.sub(r"^#{1,6}[ \t]*", "", stripped, flags=re.MULTILINE)
    # A blockquote marker is a layout cue with no spoken equivalent.
    stripped = re.sub(r"^[ \t]*>[ \t]?", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"~~(.+?)~~", r"\1", stripped)
    stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
    # Single-mark emphasis, AFTER bold so "**x**" is not read as two italics.
    # The underscore form requires non-word boundaries: snake_case identifiers
    # are content, and "user_id_value" must not lose its middle.
    stripped = re.sub(r"\*([^*\n]+)\*", r"\1", stripped)
    stripped = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", stripped)
    stripped = stripped.replace("`", "")
    # Table rows: separator lines out, cell pipes read as pauses. The
    # whitespace classes are HORIZONTAL on purpose — \s would swallow the line
    # breaks, gluing the table to what follows it and breaking every rule
    # applied after it.
    stripped = re.sub(r"^[ \t]*\|?[ \t:|-]*\|?[ \t]*$", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"[ \t]*\|[ \t]*", " · ", stripped)
    # The pipes leave pauses at the row edges — trim them, the voice does not
    # need an empty cell before the first word.
    stripped = re.sub(r"^[ \t]*·[ \t]*", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"[ \t]*·[ \t]*$", "", stripped, flags=re.MULTILINE)
    # A leading bullet read aloud is a pause, not the word "hyphen".
    stripped = re.sub(r"^[ \t]*[-*+][ \t]+", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"^[ \t]*\d+\.[ \t]+", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


# --- The mechanical ear -----------------------------------------------------------------------
#
# The synthesizer reads the written answer as it stands. What a
# synthesizer cannot read honestly is not a matter of judgment but of
# typography: markdown marks, abbreviated months, a colon spoken as a word.
# Spelling those out is deterministic — regexes, a French vocabulary, unit
# tests — which is why it lives here rather than in a second model call.
#
# The figures themselves are spoken by num2words — the industry's pragmatic
# answer for TTS text normalization (the heavyweight one, NVIDIA NeMo's WFST
# grammars, asks for linguistic tooling this feature does not need). It ships
# with the ``ai`` extra and is imported lazily: absent, the amounts still get
# their units spelled ("150 mille euros") with the figure left as digits — a
# degraded voice, never a broken one.

try:
    from num2words import num2words as _num2words
except ImportError:  # pragma: no cover - exercised through the fallback tests
    _num2words = None


def _integer_in_words(digits: str, language: str) -> str:
    """One whole number as it is said, or the digits when no library speaks."""
    if _num2words is None:
        return digits
    try:
        return _num2words(int(digits), lang=language)
    except (ValueError, NotImplementedError):
        return digits


def _number_in_words(figure: str, language: str, vocabulary: "SpeechVocabulary") -> str:
    """
    A figure as a person reads it aloud.

    The two sides of the separator are spoken as NUMBERS, not as digits: "1,48"
    is "un virgule quarante-huit", the way it is said out loud. Handing the
    whole float to num2words gives "un virgule quatre huit" — correct digits,
    and nobody says that.

    Leading zeros of the decimal part keep their place ("1,05" → "un virgule
    zéro cinq"): spoken as a number, "05" would drop the zero and say a
    hundredth as if it were a tenth.
    """
    if _num2words is None:
        return figure
    # The spaces are thousands groups ("22 860"), not part of the value.
    plain = figure.replace(" ", "").replace(".", ",")
    whole, _, decimals = plain.partition(",")
    words = _integer_in_words(whole or "0", language)
    if not decimals:
        return words

    leading_zeros = len(decimals) - len(decimals.lstrip("0"))
    zeros = [_integer_in_words("0", language)] * leading_zeros
    remainder = decimals[leading_zeros:]
    spoken_decimals = zeros + ([_integer_in_words(remainder, language)] if remainder else [])
    return f"{words} {vocabulary.decimal_separator} {' '.join(spoken_decimals)}"


# Typography a synthesizer reads as silence or as noise: the narrow no-break
# space French puts between a number and its unit ("22,8 %") or between
# thousands groups ("22 860") becomes a plain space before anything else looks
# at it. Not language-specific — the marks are typographic, not lexical.
_INVISIBLE_SPACES = str.maketrans({"\u202f": " ", "\u00a0": " "})

# One figure: thousands groups separated by spaces, a decimal comma or point,
# or a bare integer — matched so "22 860,5 M€" is one spoken amount and not
# "860".
_FIGURE_RE = r"\d{1,3}(?: \d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?"

# The scale prefixes and the currency symbols, in one amount. The currency is
# per symbol, not per country: "$" is spoken dollars whatever the issuer, and
# a currency missing from a vocabulary's table is a symbol the voice reads as
# letters — extend the table, never guess.
_AMOUNT_RE = re.compile(rf"({_FIGURE_RE})\s*(Mds|Md|M|k|K)?\s*(€|\$|£|¥|₿|CHF)")
_PERCENT_RE = re.compile(rf"({_FIGURE_RE})\s*%")

# A sign, and only a sign: the "+" or "-" that OPENS a figure. Anything glued to
# what precedes it is punctuation of that token, not an operator — "2024-01-01"
# is a date, "10-15" a range, "ref-12" an identifier, and a voice saying "moins"
# in any of them is reading something the answer never wrote.
_SIGN_RE = re.compile(r"(?<![\w)\]])([+-])(?=\d)")

# A colon the model left in despite the prompt is a voice problem: it becomes a
# comma pause, the closest thing to how a reader uses it. Two colons are NOT
# that: the one inside a time ("14:30") and the one opening a URL scheme
# ("https://") are part of their token, and turning them into a pause loses
# what the answer said.
_SPOKEN_COLON_RE = re.compile(r"\s*(?<!\d):(?!//)\s*")


@dataclass(frozen=True)
class SpeechVocabulary:
    """How one language says what typography only writes.

    Adding a language is adding one instance to :data:`_SPEECH_VOCABULARIES`,
    never another branch: the pipeline below is language-agnostic, only these
    tables are not.
    """

    #: Scale prefix -> (singular, plural) of the spoken scale word.
    scales: Dict[str, Tuple[str, str]]
    #: Currency symbol -> how it is said, already plural.
    currencies: Dict[str, str]
    #: Abbreviated month -> its full name. An abbreviation is read as letters
    #: ("nov. 2024" as "N-O-V point ...") on some engines.
    months: Dict[str, str]
    #: Layout glyphs with one natural spoken equivalent in this language.
    glyphs: List[Tuple["re.Pattern", str]]
    #: What "%" is said as, and the sign words.
    percent: str
    plus: str
    minus: str
    #: Vowel sounds triggering the elision of the scale connector, and the two
    #: connector forms ("un million d'euros" / "de dollars").
    elision_sounds: str
    elided_connector: str
    connector: str
    #: How the decimal separator is said. The part after it is spoken as ONE
    #: number ("un virgule quarante-huit"), which is how a person reads a
    #: figure — num2words says it digit by digit ("un virgule quatre huit"),
    #: which is how a machine reads one. Last of the required fields on
    #: purpose: a field inserted above one shifts every positional argument
    #: after it, silently, in every vocabulary a consuming project declares.
    decimal_separator: str
    #: The scales this language leaves invariable and un-connected ("mille").
    invariable_scales: Tuple[str, ...] = ()


_FRENCH_VOCABULARY = SpeechVocabulary(
    scales={
        "k": ("mille", "mille"),  # invariable: un mille, deux mille
        "K": ("mille", "mille"),
        "M": ("million", "millions"),
        "Md": ("milliard", "milliards"),
        "Mds": ("milliard", "milliards"),
    },
    currencies={
        "€": "euros",
        "$": "dollars",
        "£": "livres",
        "¥": "yens",
        "₿": "bitcoins",
        "CHF": "francs suisses",
    },
    months={
        "janv.": "janvier", "févr.": "février", "avr.": "avril",
        "juil.": "juillet", "sept.": "septembre", "oct.": "octobre",
        "nov.": "novembre", "déc.": "décembre",
    },
    glyphs=[
        # The ASCII arrow is what a model actually types when it thinks in
        # keyboards; the unicode one is what it types when it thinks in glyphs.
        (re.compile(r"->|→"), ", "),
        (re.compile(r"&"), " et "),
    ],
    percent="pour cent",
    plus="plus ",
    minus="moins ",
    elision_sounds="aeiouéèêh",
    elided_connector="d'",
    connector="de ",
    decimal_separator="virgule",
    invariable_scales=("k", "K"),
)

#: The vocabularies the framework ships. A language absent from here gets the
#: markdown strip alone — a degraded voice, never another language's words.
_SPEECH_VOCABULARIES: Dict[str, SpeechVocabulary] = {
    "fr": _FRENCH_VOCABULARY,
}


def _spell_amount(match: "re.Match", language: str, vocabulary: SpeechVocabulary) -> str:
    """One figure, its scale and its currency, as they are said."""
    figure, scale, currency = match.group(1), match.group(2), match.group(3)
    words = _number_in_words(figure, language, vocabulary)
    currency_words = vocabulary.currencies.get(currency, currency)
    if not scale:
        return f"{words} {currency_words}"
    singular, plural = vocabulary.scales[scale]
    if scale in vocabulary.invariable_scales:
        # Invariable, and never followed by a connector: "cent cinquante mille
        # euros".
        return f"{words} {singular} {currency_words}"
    value = float(figure.replace(" ", "").replace(",", "."))
    # The agreement follows the SPOKEN number: "un million", "un virgule cinq
    # millions". The elision is the currency's first sound: "d'euros",
    # "de dollars".
    scale_word = singular if value == 1 else plural
    connector = (
        vocabulary.elided_connector
        if currency_words[0] in vocabulary.elision_sounds
        else vocabulary.connector
    )
    return f"{words} {scale_word} {connector}{currency_words}"


def normalize_speech(text: str, language: Optional[str] = None) -> str:
    """
    Make a written answer honest to read aloud — mechanically.

    The markdown goes first: a synthesized "**500 k€**" is asterisks and a
    composed unit, and the amounts are matched after the marks are gone.
    Bare digits are LEFT AS DIGITS — engines read "2024" correctly, and a
    text without any figure is harder to follow than one with them. A digit
    carrying a unit (amount, percent) is different: the unit announces the
    number, so the whole thing is said — "vingt-deux virgule huit millions
    d'euros", "vingt-six pour cent".

    Args:
        text: The written answer, markdown included.
        language: The spoken vocabulary to apply, as configured in
            ``chatbot.spoken_block.language``. None, or a language the
            framework ships no vocabulary for, gets the markdown strip alone
            rather than another language's words.

    Returns:
        The text a synthesizer can read as it stands.
    """
    stripped = strip_markdown_for_speech(text).translate(_INVISIBLE_SPACES)
    vocabulary = _SPEECH_VOCABULARIES.get(language) if language else None
    if vocabulary is None:
        return stripped

    # The signed figures are unmarked before their amounts and percents are
    # spelled: after the spelling the "+" is glued to letters and no longer
    # recognizable as a sign.
    stripped = _SIGN_RE.sub(
        lambda m: vocabulary.plus if m.group(1) == "+" else vocabulary.minus, stripped
    )
    stripped = _AMOUNT_RE.sub(lambda m: _spell_amount(m, language, vocabulary), stripped)
    stripped = _PERCENT_RE.sub(
        lambda m: f"{_number_in_words(m.group(1), language, vocabulary)} {vocabulary.percent}", stripped
    )
    for pattern, spoken in vocabulary.glyphs:
        stripped = pattern.sub(spoken, stripped)
    stripped = _SPOKEN_COLON_RE.sub(", ", stripped)
    for abbreviation, month in vocabulary.months.items():
        stripped = stripped.replace(abbreviation, month)
    # The replacements leave commas against commas (" : " after an arrow
    # became ", , "): one pause, not a stumble.
    stripped = re.sub(r",\s*,", ",", stripped)
    stripped = re.sub(r"\s+,", ",", stripped)
    return re.sub(r"  +", " ", stripped).strip()


def split_complete_sentences(buffer: str) -> Tuple[List[str], str]:
    """
    Cut a growing spoken block into speakable pieces.

    A sentence ends at terminal punctuation followed by whitespace, or at a
    line break — the break matters as much as the period: answers carry short
    lists whose lines end without punctuation, and a paragraph break is a
    natural speech pause even mid-sentence.

    A period closing a figure does NOT end a sentence: "1." opening an ordered
    list, or "2024." closing one, would otherwise be cut into a piece of its
    own and read aloud as a bare number. The piece simply joins the text that
    follows it, which is what a reader does with it.
    """
    parts = re.split(r"(?<=[.!?…])(?<!\d\.)[ \t]+|\n+", buffer)
    if len(parts) <= 1:
        return [], buffer
    return parts[:-1], parts[-1]


class SpokenBlockPipeline:
    """
    The voice, as the conversation service wires it.

    Spoken pieces go in one end, ``voice`` SSE events (base64 PCM chunks) come
    out the other — synthesized sentence by sentence WHILE the rest of the
    answer is still generating. A single worker keeps the order: several
    voices at once is a bug, not a feature.

    The caller drives the drains: after every upstream event it yields
    whatever is ready (:meth:`drain`), and at the end of the turn it waits for
    the tail (:meth:`finish`). A synthesis failure never breaks the chat: one
    error event, then silence — the text stream carries on alone.
    """

    def __init__(self, synthesize: Callable[[str], AsyncIterator[bytes]]):
        self._synthesize = synthesize
        self._sentence_buffer = ""
        self._sentences: "asyncio.Queue[str]" = asyncio.Queue()
        self._audio: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
        self._worker: Optional[asyncio.Task] = None
        self._error_emitted = False
        self._draining = False

    def feed(self, text: str) -> None:
        """Add one spoken piece; complete sentences queue for the worker."""
        self._ensure_worker()
        self._sentence_buffer += text
        complete, self._sentence_buffer = split_complete_sentences(self._sentence_buffer)
        for sentence in complete:
            self._sentences.put_nowait(sentence)

    async def drain(self) -> AsyncIterator[str]:
        """Yield the audio that became ready since the last drain."""
        if self._draining:
            return
        self._draining = True
        try:
            while not self._audio.empty():
                chunk = self._audio.get_nowait()
                if chunk is None:
                    return
                if chunk == "\0error":
                    yield format_sse("voice", {"error": "synthesis"})
                    continue
                yield format_sse("voice", {"audio": chunk})
        finally:
            self._draining = False

    async def finish(self) -> AsyncIterator[str]:
        """End of turn: speak the remainder, then wait for the worker's end."""
        if self._worker is None:
            return
        if self._sentence_buffer.strip():
            self._sentences.put_nowait(self._sentence_buffer)
            self._sentence_buffer = ""
        self._sentences.put_nowait(None)
        while True:
            chunk = await self._audio.get()
            if chunk is None:
                break
            if chunk == "\0error":
                yield format_sse("voice", {"error": "synthesis"})
                continue
            yield format_sse("voice", {"audio": chunk})
        try:
            await self._worker
        finally:
            self._worker = None

    async def abort(self) -> None:
        """Drop everything: the client disconnected, the voice stops mid-air."""
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - teardown
                pass
            self._worker = None
        self._sentence_buffer = ""

    def _ensure_worker(self) -> None:
        if self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            sentence = await self._sentences.get()
            if sentence is None:
                self._audio.put_nowait(None)
                return
            try:
                async for chunk in self._synthesize(sentence):
                    self._audio.put_nowait(base64.b64encode(chunk).decode("ascii"))
            except Exception as e:  # noqa: BLE001 - the chat must survive the voice
                logger.error(f"Sentence synthesis failed: {e}")
                if not self._error_emitted:
                    self._error_emitted = True
                    self._audio.put_nowait("\0error")
