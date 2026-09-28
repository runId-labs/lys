"""
Tests for the chatbot's spoken answer — the direct voice.

One text, said as it stands: the normalizer is the mechanical ear (markdown
out, amounts and symbols spelled), the pipeline synthesizes it sentence by
sentence while the answer is still generating.
"""
import pytest

from lys.apps.ai.modules.conversation.spoken_block import (
    SpokenBlockConfig,
    SpokenBlockPipeline,
    normalize_speech,
    split_complete_sentences,
    strip_markdown_for_speech,
)


def test_disabled_config_leaves_no_voice():
    """The feature is opt-in: an app that configures nothing has none."""
    config = SpokenBlockConfig.from_plugin_config({})
    assert config.enabled is False


def test_a_partial_enabled_config_is_enough():
    """Only ``enabled`` decides existence: ``{"enabled": True}`` is a working
    voice with nothing else."""
    config = SpokenBlockConfig.from_plugin_config({"spoken_block": {"enabled": True}})
    assert config.enabled is True


def test_the_stripper_removes_what_a_voice_cannot_read():
    stripped = strip_markdown_for_speech("## Head\n**bold** and *italic* and `code`")
    assert stripped == "Head\nbold and italic and code"


def test_the_stripper_drops_link_urls_and_keeps_their_text():
    stripped = strip_markdown_for_speech("See [the report](http://x.y) for details")
    assert "the report" in stripped
    assert "http" not in stripped


def test_the_stripper_keeps_snake_case_identifiers_whole():
    """The underscore form needs non-word boundaries: user_id_value is content."""
    assert strip_markdown_for_speech("_user_id_value_") == "_user_id_value_"


def test_the_stripper_keeps_a_bare_url():
    """This function only strips marks, never content: a URL in the prose stays."""
    assert strip_markdown_for_speech("go to http://x.y") == "go to http://x.y"


# --- The mechanical ear ---------------------------------------------------------

def test_an_amount_is_said_in_words_with_its_unit():
    """150 k€ is one spoken amount: the figure in words, the scale, the
    currency. The unit announces the number, so both are said."""
    spoken = normalize_speech(
        "Le CA est de **22,8 M€**, en hausse de +26%, arrêté au 15 nov. 2024.", "fr"
    )
    assert "vingt-deux virgule huit millions d'euros" in spoken
    assert "plus vingt-six pour cent" in spoken
    assert "15 novembre 2024" in spoken
    # The markdown marks are gone: a synthesizer never hears an asterisk.
    assert "**" not in spoken


def test_a_signed_percent_is_said_with_its_sign():
    spoken = normalize_speech("+26% de hausse, -12% de marge", "fr")
    assert "plus vingt-six pour cent" in spoken
    assert "moins douze pour cent" in spoken


def test_every_scale_of_an_amount_agrees_with_its_figure():
    """The agreement follows the SPOKEN number: one million, one and a half
    millions. The thousand scale never carries a "de"."""
    spoken = normalize_speech("1 M€, 1,5 M€, 2 Md€, 500 k€, 150 k€", "fr")
    assert "un million d'euros" in spoken
    assert "un virgule cinq millions d'euros" in spoken
    assert "deux milliards d'euros" in spoken
    assert "cinq cents mille euros" in spoken
    assert "cent cinquante mille euros" in spoken


def test_the_amount_currencies_are_spoken_by_symbol():
    """The currency is per symbol: dollars, livres, yens, bitcoins, francs
    suisses — the voice says what the figure carries, whatever the issuer."""
    spoken = normalize_speech("3 M$, 1 M£, 120 ¥, 0,5 ₿, 120 CHF", "fr")
    assert "trois millions de dollars" in spoken
    assert "un million de livres" in spoken
    assert "cent vingt yens" in spoken
    assert "zéro virgule cinq bitcoins" in spoken
    assert "cent vingt francs suisses" in spoken


def test_the_thousands_spaces_are_part_of_the_figure():
    """French groups thousands with spaces: "22 860 €" is one amount, not
    "860" said alone."""
    spoken = normalize_speech("La trésorerie est de 22 860 €", "fr")
    assert "vingt-deux mille huit cent soixante euros" in spoken


def test_bare_digits_are_left_to_the_engine():
    """Digits without a unit stay as digits: engines read numbers correctly,
    and the amounts carry the units that announce them."""
    spoken = normalize_speech("en 2024, 150 salariés, un ETP de 22,8", "fr")
    assert "2024" in spoken
    assert "150" in spoken
    assert "22,8" in spoken


def test_a_colon_becomes_a_pause():
    """A colon is read as a word by naive engines: the pause a reader means
    by it is a comma."""
    spoken = normalize_speech("SF : liquidité au plancher", "fr")
    assert spoken == "SF, liquidité au plancher"


def test_the_arrow_is_a_pause_not_a_colon():
    spoken = normalize_speech("SF -> liquidité : 21 k€", "fr")
    assert "SF, liquidité, vingt et un mille euros" in spoken


def test_the_french_typography_spaces_do_not_break_the_amounts():
    """A narrow no-break space before the unit is silence or noise to an
    engine — it becomes a plain space before anything else reads it."""
    spoken = normalize_speech("26\u202f% du chiffre d'affaires", "fr")
    assert "vingt-six pour cent" in spoken


def test_without_the_library_the_figures_stay_as_digits():
    """num2words is optional: absent, the units are still spelled and the
    voice degrades to digits — it never breaks."""
    import lys.apps.ai.modules.conversation.spoken_block as spoken_block
    saved = spoken_block._num2words
    try:
        spoken_block._num2words = None
        spoken = spoken_block.normalize_speech("150 k€ et 26%", "fr")
        assert "150 mille euros" in spoken
        assert "26 pour cent" in spoken
    finally:
        spoken_block._num2words = saved


def test_the_mechanical_ear_of_an_unknown_language_is_only_markdown():
    """The framework ships no vocabulary for that language: the strip alone,
    never another language's words."""
    spoken = normalize_speech("26% and **bold**", language="en")
    assert spoken == "26% and bold"


def test_an_unconfigured_language_speaks_no_vocabulary():
    """The default is no vocabulary at all: an app that declares no
    ``spoken_block.language`` gets the markdown strip, not French."""
    assert normalize_speech("26% et **gras**") == "26% et gras"


def test_the_config_carries_the_spoken_vocabulary():
    """The language is one plugin-config line, lowercased — the framework
    hardcodes none."""
    assert SpokenBlockConfig.from_plugin_config(
        {"spoken_block": {"enabled": True, "language": "FR"}}
    ) == SpokenBlockConfig(enabled=True, language="fr")
    assert SpokenBlockConfig.from_plugin_config(
        {"spoken_block": {"enabled": True}}
    ).language is None


def test_a_url_keeps_its_scheme_and_a_time_its_colon():
    """The colon pause must not eat a token's own colon: a spoken
    "https, //" and a "14, 30" both lose what the answer said."""
    spoken = normalize_speech("Voir https://exemple.fr/doc à 14:30, ratio 3:1", "fr")
    assert "https://exemple.fr/doc" in spoken
    assert "14:30" in spoken
    assert "3:1" in spoken


def test_a_hyphen_inside_a_token_is_not_a_minus_sign():
    """A date, a range and an identifier all carry hyphens that are
    punctuation, not operators: only a sign OPENING a figure is spoken."""
    spoken = normalize_speech("Du 2024-01-01 au 2024-03-31, sur 10-15 jours (ref-12)", "fr")
    assert "moins" not in spoken
    assert "2024-01-01" in spoken
    assert "10-15" in spoken
    assert "ref-12" in spoken


def test_a_sign_opening_a_figure_is_still_spoken():
    """The guard above must not mute the real signs."""
    spoken = normalize_speech("Marge +12 % contre -3 %", "fr")
    assert "plus douze pour cent" in spoken
    assert "moins trois pour cent" in spoken


def test_an_ordered_list_marker_is_not_spoken_as_a_bare_number():
    """The sentence split runs before the markdown strip: a period closing a
    figure must not cut "1." into a piece read aloud as "un"."""
    sentences, remainder = split_complete_sentences("1. Premier point. 2. Second point. ")
    assert sentences == ["1. Premier point.", "2. Second point."]
    assert normalize_speech(sentences[0], "fr") == "Premier point."


@pytest.mark.asyncio
async def test_the_pipeline_synthesizes_sentence_by_sentence_in_order():
    """The sentences are synthesized in arrival order, one call each."""
    synthesized = []

    async def fake_synthesize(sentence: str):
        synthesized.append(sentence)
        yield b"audio"

    pipeline = SpokenBlockPipeline(fake_synthesize)
    pipeline.feed("Première phrase. ")
    pipeline.feed("Deuxième phrase. ")
    pipeline.feed("Troisième en attente")
    async for _ in pipeline.drain():
        pass
    async for _ in pipeline.finish():
        pass

    assert synthesized == ["Première phrase.", "Deuxième phrase.", "Troisième en attente"]


@pytest.mark.asyncio
async def test_a_failing_synthesis_emits_one_error_and_ends_cleanly():
    """A synthesis failure never breaks the chat: one error event, then
    silence — the text stream carries on alone."""
    async def failing_synthesize(sentence: str):
        raise RuntimeError("boom")
        yield b""

    pipeline = SpokenBlockPipeline(failing_synthesize)
    pipeline.feed("Une phrase.")
    events = []
    async for event in pipeline.finish():
        events.append(event)
    assert any('"error": "synthesis"' in event for event in events)
