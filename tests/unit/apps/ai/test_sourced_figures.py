"""The check of an analysis's figures against what its run read (utils/sourced_figures.py)."""
from lys.apps.ai.utils.sourced_figures import MAX_REPORTED, context_of, unsourced_figures

SOURCES = [
    '{"content": "| 2030 | 1250000 | 1000000 | 210000 | 21.0% |\\nTresorerie point bas 318462 €"}',
    '{"results": [{"name": "rate", "expression": "210000 / 1000000", "value": "0.21"}]}',
    "Question : la masse salariale 2030 et le taux a 12,31 €/h",
]


def _missing(analysis):
    return [figure.text for figure in unsourced_figures(analysis, SOURCES)]


class TestFound:

    def test_figures_read_written_rounded_or_scaled_are_found(self):
        assert _missing("Masse 1 000 000 €, coût 1 250 k€, point bas 318 462 €, soit 318 k€.") == []

    def test_a_percentage_is_found_as_written_or_as_the_ratio_computed(self):
        assert _missing("Taux 21,0 % ; taux effectif 21 %.") == []

    def test_a_figure_of_the_question_is_found(self):
        assert _missing("Au taux de 12,31 €/h.") == []

    def test_years_dates_and_short_numbers_are_not_checked(self):
        assert _missing("En 2030, au 31/05/2030, sur 12 mois et 9 sites, +5 %.") == []


class TestMissing:

    def test_a_figure_read_nowhere_is_reported_with_its_context(self):
        analysis = "La trésorerie hors pic va de 318 k€ à 50 860 € sur l'année."
        missing = unsourced_figures(analysis, SOURCES)
        assert [figure.text for figure in missing] == ["50 860"]
        assert "50 860" in context_of(analysis, missing[0])

    def test_a_sum_made_in_the_head_is_reported(self):
        assert _missing("Les trois prestataires font ~9 330 € au total.") == ["9 330"]

    def test_a_close_but_different_figure_is_reported(self):
        assert _missing("Point bas 320 000 €.") == ["320 000"]

    def test_reports_are_bounded(self):
        analysis = " ".join(f"{100000 + index * 1000} €" for index in range(MAX_REPORTED + 5))
        assert len(unsourced_figures(analysis, SOURCES)) == MAX_REPORTED
