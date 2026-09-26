"""
Tests for the spoken blocks — the written/spoken split of a chatbot answer.

What is tested: the pure blocks of the mechanism. The tags route a token
stream into written and spoken pieces (including the tag cut in half across
two chunks), the persistence split keeps the written content free of tags, and
the fallback sanitizer makes a written answer honest to the ear. No provider,
no socket.
"""

import pytest

from lys.apps.ai.modules.conversation.spoken_block import (
    SpokenBlockConfig,
    SpokenBlockPipeline,
    SpokenBlockSplitter,
    split_spoken_blocks,
    spoken_fallback_opening,
    strip_markdown_for_speech,
)


def renditions(splits: list[str]) -> tuple[str, str]:
    """Feed a splitter every piece, returning its written and spoken texts."""
    splitter = SpokenBlockSplitter(SpokenBlockConfig(enabled=True))
    pieces: list[tuple[str, str]] = []
    for text in splits:
        pieces.extend(splitter.feed(text))
    pieces.extend(splitter.flush())
    written = "".join(text for kind, text in pieces if kind == "written")
    spoken = "".join(text for kind, text in pieces if kind == "voice")
    return written, spoken


def test_disabled_config_leaves_the_answer_whole():
    config = SpokenBlockConfig.from_plugin_config({})
    written, spoken = split_spoken_blocks("[VOICE]Bonjour tout le monde[/VOICE] Écrit.", config)

    assert config.enabled is False
    assert written == "[VOICE]Bonjour tout le monde[/VOICE] Écrit."
    assert spoken is None


def test_a_partial_enabled_config_uses_the_framework_defaults():
    config = SpokenBlockConfig.from_plugin_config({"spoken_block": {"enabled": True}})

    assert config.enabled is True
    assert config.open_tag == "[VOICE]"
    assert config.close_tag == "[/VOICE]"
    assert config.prompt  # the framework's default instructions


def test_a_block_splits_the_stream_into_written_and_voice():
    written, spoken = renditions([
        "Answer written. [VOICE]Spoken summary",
        " of the answer.[/VOICE] Written tail.",
    ])

    assert " ".join(written.split()) == "Answer written. Written tail."
    assert spoken == "Spoken summary of the answer."


def test_a_tag_cut_in_half_across_chunks_is_reassembled():
    """The provider may emit "[VO" and "ICE]" in separate chunks — the held-back
    tail must become a tag, never a stray "[VO" in either rendition."""
    written, spoken = renditions(["Written start. [VO", "ICE]Spoken[/VO", "ICE] Tail."])

    assert " ".join(written.split()) == "Written start. Tail."
    assert spoken == "Spoken"
    assert "[VO" not in written + spoken


def test_an_unclosed_block_is_still_spoken_content():
    """The model was interrupted mid-block, not undecided about speaking."""
    written, spoken = renditions("[VOICE]I am pulling the hea")

    assert written == ""
    assert spoken == "I am pulling the hea"


def test_persistence_split_keeps_content_free_of_tags():
    written, spoken = split_spoken_blocks(
        "Written answer, complete.\n\n[VOICE]Spoken rendition, two sentences. Numbers said aloud.[/VOICE]",
        SpokenBlockConfig(enabled=True),
    )

    assert written == "Written answer, complete."
    assert spoken == "Spoken rendition, two sentences. Numbers said aloud."


def test_persistence_split_without_a_block_is_the_written_answer():
    written, spoken = split_spoken_blocks("Just text, no block.", SpokenBlockConfig(enabled=True))

    assert written == "Just text, no block."
    assert spoken is None  # the drift signal


def test_two_blocks_are_joined_in_the_spoken_side():
    written, spoken = split_spoken_blocks(
        "A [VOICE]first[/VOICE] B [VOICE]second[/VOICE] C",
        SpokenBlockConfig(enabled=True),
    )
    assert " ".join(written.split()) == "A B C"
    assert spoken == "first\n\nsecond"


def test_custom_tags_are_honored():
    config = SpokenBlockConfig(enabled=True, open_tag="<say>", close_tag="</say>")
    written, spoken = split_spoken_blocks("Texte <say>Parlé</say> Suite.", config)

    assert " ".join(written.split()) == "Texte Suite."
    assert spoken == "Parlé"


def test_the_fallback_stripper_removes_what_a_voice_cannot_read():
    stripped = strip_markdown_for_speech(
        "### Titre\n\nLe solde est de **622 342 €** et `croît`.\n\n"
        "| Société | Trésorerie |\n|---|---|\n| A | 8 k€ |\n| B | 107 k€ |\n\n"
        "- premier point\n- deuxième point\n1. numéroté"
    )

    assert "###" not in stripped
    assert "**" not in stripped
    assert "`" not in stripped
    assert "|" not in stripped
    assert stripped.startswith("Titre")
    assert "A · 8 k€" in stripped  # a table read aloud is a list, not a grid
    assert "- " not in stripped
    assert "1. " not in stripped
    assert "622 342 €" in stripped  # the figures survive, only the marks go


def test_the_fallback_reading_keeps_only_the_opening_sentences():
    """Drift must not turn into a two-minute reading of the whole answer."""
    opening = spoken_fallback_opening(
        "Premier point, le verdict. Deuxième phrase utile.\n"
        "Troisième phrase encore. Une quatrième utile aussi. Une cinquième qui passe.\n"
        "Une sixième déjà trop. Et un paragraphe entier que personne n'écoutera."
    )

    assert opening == (
        "Premier point, le verdict. Deuxième phrase utile. "
        "Troisième phrase encore. Une quatrième utile aussi. Une cinquième qui passe."
    )


def test_the_fallback_reading_of_a_short_answer_is_whole():
    opening = spoken_fallback_opening("Une seule phrase courte")

    assert opening == "Une seule phrase courte"


@pytest.mark.asyncio
async def test_the_pipeline_synthesizes_sentence_by_sentence_in_order():
    synthesized: list[str] = []

    async def fake_synthesize(sentence: str):
        synthesized.append(sentence)
        yield b"\x01"

    pipeline = SpokenBlockPipeline(fake_synthesize)
    pipeline.feed("First sentence. Second sentence. Third, still grow")
    # Nothing is ready at feed time — the worker has had no turn to run.
    drained_now = [event async for event in pipeline.drain()]
    assert drained_now == []

    events = [event async for event in pipeline.finish()]
    # Everything fed was spoken, the remainder included, in order.
    assert synthesized == ["First sentence.", "Second sentence.", "Third, still grow"]
    assert len(events) == 3
    assert '"audio"' in events[0]


@pytest.mark.asyncio
async def test_a_failing_synthesis_emits_one_error_and_ends_cleanly():
    async def failing(sentence: str):
        raise RuntimeError("provider down")
        yield b""  # pragma: no cover — makes this an async generator

    pipeline = SpokenBlockPipeline(failing)
    pipeline.feed("One sentence. Another one.")
    events = [event async for event in pipeline.finish()]

    # ONE error marker for the whole feed, not one per sentence.
    assert events == ['event: voice\ndata: {"error": "synthesis"}\n\n']
