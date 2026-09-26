"""
Spoken-block support for the chatbot — the written/spoken split.

A chatbot answer can carry TWO renditions of itself: the written one, displayed
in the chat, and a spoken one meant for a voice. The convention carrying both
in the model's single output channel: the spoken rendition is wrapped in tags
declared in configuration — ``[VOICE]...[/VOICE]`` by default — and may appear
ANYWHERE in the stream: a short block before a tool call ("what I am looking
at"), a full block as the answer's spoken summary.

Everything here is generic framework mechanism, no application content: which
tags, what instructions the model gets (a default prompt, overridable), and
whether the feature exists at all are all ``chatbot.spoken_block`` settings —
an app that configures nothing keeps the exact behavior it had. The voice of
the answers (persona, language style) stays in the app's own prompt.

Pure blocks only, no provider and no socket: unit-testable without a TTS key.
"""

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# What one line of configuration looks like. Absent or ``enabled: false`` means
# the feature does not exist: no prompt injected, no tag routing, no split at
# persistence — the answer is what the model wrote, whole.
DEFAULT_SPOKEN_BLOCK_OPEN_TAG = "[VOICE]"
DEFAULT_SPOKEN_BLOCK_CLOSE_TAG = "[/VOICE]"

# The default instructions injected in the system prompt when the feature is
# on. English — tags and instructions in the same language as the tags, the
# spoken CONTENT staying in the conversation's language; an app replaces the
# whole section through ``chatbot.spoken_block.prompt`` when its voice needs
# a persona of its own.
DEFAULT_SPOKEN_BLOCK_PROMPT = f"""# Voice output

Your answers are read aloud by a speech synthesizer. EVERY answer — including
long, structured ones — opens with its spoken rendition wrapped in {DEFAULT_SPOKEN_BLOCK_OPEN_TAG}...{DEFAULT_SPOKEN_BLOCK_CLOSE_TAG} tags.
An answer without one leaves the reader with silence.

The spoken rendition is the answer FOR THE EAR, and it stands alone: everything
the written answer establishes that the reader needs — names, figures,
definitions, warnings — is said aloud. Someone who only listens must never have
to re-ask what the written text already said.

- Length follows the content: a terse question earns a sentence or two, a rich
  answer earns as many as it needs. Conversational, never a reading of the full
  text: say the substance, skip the layout talk.
- Plain text only inside the tags: no bold, no headings, no tables. Short lists
  are allowed when they genuinely help the ear — naming the four dimensions of
  an index aloud, for instance.
- Write EVERY number, amount and symbol the way it is SPOKEN, in full words:
  "about twenty-two point eight million euros", never "22,8 M€". Spell units
  and symbols out — "%" becomes "percent", "€" becomes "euros" — in the
  conversation's language. A synthesizer reads what a page writes literally.
- You may ALSO open a short spoken block BEFORE a slow tool call to say what
  you are looking at ("I am pulling the health scores of the six companies")
  — the reader hears you are working instead of staring at silence.
- Outside the tags, write the complete answer as usual: the block carries the
  speech, never replaces the text."""

# The repair instructions used when a turn carried the voice but the model
# wrote no block — a focused LLM call regenerates what the model skipped.
# Configurable through the tts endpoint (``tts.options.repair_prompt``): the
# voice's repair is the voice's business, and an app may want its repair to
# speak in a persona of its own.
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


@dataclass(frozen=True)
class SpokenBlockConfig:
    """The feature's configuration, resolved from the AI plugin settings."""

    enabled: bool = False
    open_tag: str = DEFAULT_SPOKEN_BLOCK_OPEN_TAG
    close_tag: str = DEFAULT_SPOKEN_BLOCK_CLOSE_TAG
    prompt: str = DEFAULT_SPOKEN_BLOCK_PROMPT

    @classmethod
    def from_plugin_config(cls, chatbot_config: Dict) -> "SpokenBlockConfig":
        """
        Read ``chatbot.spoken_block`` from the AI plugin configuration.

        A partial dict is fine — only ``enabled`` truly decides existence, the
        rest falls back to the framework defaults so an app that only says
        ``{"enabled": true}`` gets a working feature with nothing else.
        """
        raw = chatbot_config.get("spoken_block") or {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            open_tag=str(raw.get("open_tag") or DEFAULT_SPOKEN_BLOCK_OPEN_TAG),
            close_tag=str(raw.get("close_tag") or DEFAULT_SPOKEN_BLOCK_CLOSE_TAG),
            prompt=str(raw.get("prompt") or DEFAULT_SPOKEN_BLOCK_PROMPT),
        )


class SpokenBlockSplitter:
    """
    Cut a token stream into its written and spoken renditions.

    The tags can arrive split across chunks — ``[VO`` at the end of one, ``ICE]``
    at the start of the next — so every unemitted tail that could still become
    a tag is held back until more text decides. Everything emitted is final.

    Feed token deltas in, get ``(kind, text)`` pieces out: ``"voice"`` inside a
    block, ``"written"`` outside. The tags themselves are consumed, never
    emitted: the caller never forwards them to a client or a synthesizer.
    """

    def __init__(self, config: SpokenBlockConfig):
        self._config = config
        self._inside_block = False
        self._pending = ""

    def feed(self, text: str) -> List[Tuple[str, str]]:
        """Add one token delta, returning the completed pieces in order."""
        self._pending += text
        pieces: List[Tuple[str, str]] = []

        while True:
            tag = self._config.close_tag if self._inside_block else self._config.open_tag
            index = self._pending.find(tag)
            if index == -1:
                break
            # Text before the tag belongs to the current state; the tag itself
            # is consumed as the state switch.
            before = self._pending[:index]
            if before:
                pieces.append(("voice" if self._inside_block else "written", before))
            self._inside_block = not self._inside_block
            self._pending = self._pending[index + len(tag):]

        # No full tag left: emit everything except a tail short enough to
        # still become one. A tail longer than any tag cannot be a tag start,
        # so it is safe to release.
        hold = max(len(self._config.open_tag), len(self._config.close_tag)) - 1
        release = len(self._pending) - hold
        if release > 0:
            emitted, self._pending = self._pending[:release], self._pending[release:]
            pieces.append(("voice" if self._inside_block else "written", emitted))
        return pieces

    def flush(self) -> List[Tuple[str, str]]:
        """End of stream: whatever is held back belongs to the current state."""
        if not self._pending:
            return []
        piece = ("voice" if self._inside_block else "written", self._pending)
        self._pending = ""
        return [piece]

    @property
    def inside_block(self) -> bool:
        """True while the last fed text sits inside the spoken tags."""
        return self._inside_block


def split_spoken_blocks(text: str, config: SpokenBlockConfig) -> Tuple[str, Optional[str]]:
    """
    Split a complete answer for persistence: (written, spoken).

    The written rendition is the answer with its blocks and tags removed —
    clean for search, compaction and the next turn's history. The spoken one
    is the blocks' content joined by a blank line; ``None`` when the model
    wrote no block at all (the caller's drift signal).

    A block left unclosed at the end is still spoken content — the model was
    interrupted, not undecided — so it goes to the spoken side, tags stripped.

    A disabled configuration is a feature that does not exist: the text comes
    back exactly as written, spoken ``None`` — the guard lives here, not only
    at the call sites, so no unguarded caller can ever strip a disabled app's
    answers.
    """
    if not config.enabled:
        return text, None
    splitter = SpokenBlockSplitter(config)
    pieces = splitter.feed(text) + splitter.flush()
    written = "".join(text_ for kind, text_ in pieces if kind == "written")
    spoken_parts = [text_ for kind, text_ in pieces if kind == "voice"]
    return written.strip(), "\n\n".join(speaker.strip() for speaker in spoken_parts if speaker.strip()) or None


# Markdown that would be heard as noise or read as symbols if handed raw to a
# synthesizer. The spoken blocks should need none of this — the strip exists
# for the FALLBACK path, where the voice reads the written answer because the
# model emitted no block at all.
def strip_markdown_for_speech(text: str) -> str:
    """
    Reduce a written answer to something a voice can read honestly.

    Headings lose their markers, bold and inline code lose their marks, table
    rows become "cell · cell · cell" — a table read aloud is a list, not a
    grid — and list bullets become spoken enumeration.
    """
    stripped = text
    stripped = re.sub(r"^#{1,6}[ \t]*", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
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


def strip_spoken_tags(text: str, config: SpokenBlockConfig) -> str:
    """
    Remove the block tags a REPAIR output must not carry.

    The repair prompt says "no tags", but a model that just failed to follow
    the block convention once already is not trusted on a second instruction:
    the defensive strip is one line, a spoken "[VOICE]" aloud is a bug the
    listener hears.
    """
    return text.replace(config.open_tag, "").replace(config.close_tag, "")


def spoken_fallback_opening(text: str, max_sentences: int = 5) -> str:
    """
    The fallback reading when the model wrote no block: the OPENING of the
    written answer, not all of it.

    The drift already costs the reader a late voice; making them listen to a
    two-minute reading of a long written answer turns a miss into a punishment.
    But too short an opening zaps what the answer actually said — five
    sentences carry both the verdict and what supports it. The rest is what
    the panel is for.

    The input is a COMPLETE answer, not a streaming buffer: its final
    sentence has no closing boundary, so the tail counts as a sentence —
    nothing of what is read is dropped for a punctuation technicality.
    """
    complete, remainder = split_complete_sentences(text)
    sentences = complete + ([remainder.strip()] if remainder.strip() else [])
    return " ".join(sentence.strip() for sentence in sentences[:max_sentences]).strip()


def format_sse(event: str, data: Dict) -> str:
    """Format one SSE event — the conversation service's wire format."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def split_complete_sentences(buffer: str) -> Tuple[List[str], str]:
    """
    Cut a growing spoken block into speakable pieces.

    A sentence ends at terminal punctuation followed by whitespace, or at a
    line break — the break matters as much as the period: spoken blocks carry
    short lists whose lines end without punctuation, and a paragraph break is
    a natural speech pause even mid-sentence.
    """
    parts = re.split(r"(?<=[.!?…])[ \t]+|\n+", buffer)
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
