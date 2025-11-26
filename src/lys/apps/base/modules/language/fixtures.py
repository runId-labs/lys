"""
Fixtures for language data.
"""

from lys.apps.base.modules.language.consts import FRENCH_LANGUAGE, ENGLISH_LANGUAGE
from lys.apps.base.modules.language.services import LanguageService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LanguageFixtures(EntityFixtures[LanguageService]):
    """
    Fixtures for available languages.

    French is set as default (enabled=True by default).
    """
    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": FRENCH_LANGUAGE,
            "attributes": {
                "enabled": True,
                "description": "French language for user interface and email communications."
            }
        },
        {
            "id": ENGLISH_LANGUAGE,
            "attributes": {
                "enabled": True,
                "description": "English language for user interface and email communications."
            }
        }
    ]
