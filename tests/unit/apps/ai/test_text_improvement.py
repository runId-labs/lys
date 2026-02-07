"""
Unit tests for AI text improvement module.
"""
import inspect


class TestTextImprovementServiceStructure:
    """Tests for TextImprovementService class structure."""

    def test_service_exists(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService
        assert TextImprovementService is not None

    def test_has_improve_method(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService
        assert hasattr(TextImprovementService, "improve")
        assert inspect.iscoroutinefunction(TextImprovementService.improve)


class TestImproveTextInputModel:
    """Tests for ImproveTextInputModel Pydantic model."""

    def test_model_exists(self):
        from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel
        assert ImproveTextInputModel is not None

    def test_has_text_field(self):
        from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel
        assert "text" in ImproveTextInputModel.model_fields

    def test_has_context_field(self):
        from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel
        assert "context" in ImproveTextInputModel.model_fields

    def test_has_language_field(self):
        from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel
        assert "language" in ImproveTextInputModel.model_fields

    def test_valid_input(self):
        from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel
        model = ImproveTextInputModel(
            text="Hello world",
            context="email",
            language="en"
        )
        assert model.text == "Hello world"
        assert model.context == "email"
        assert model.language == "en"


class TestTextImprovementConsts:
    """Tests for text improvement constants."""

    def test_system_prompt_exists(self):
        from lys.apps.ai.modules.text_improvement.consts import TEXT_IMPROVEMENT_SYSTEM_PROMPT
        assert TEXT_IMPROVEMENT_SYSTEM_PROMPT is not None
        assert isinstance(TEXT_IMPROVEMENT_SYSTEM_PROMPT, str)
        assert len(TEXT_IMPROVEMENT_SYSTEM_PROMPT) > 0


class TestImprovedTextNode:
    """Tests for ImprovedTextNode GraphQL node."""

    def test_node_exists(self):
        from lys.apps.ai.modules.text_improvement.nodes import ImprovedTextNode
        assert ImprovedTextNode is not None

    def test_has_improved_text_field(self):
        from lys.apps.ai.modules.text_improvement.nodes import ImprovedTextNode
        annotations = {}
        for cls in ImprovedTextNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "improved_text" in annotations

    def test_has_message_field(self):
        from lys.apps.ai.modules.text_improvement.nodes import ImprovedTextNode
        annotations = {}
        for cls in ImprovedTextNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "message" in annotations


class TestAIModulesInit:
    """Tests for AI modules __init__.py submodules list."""

    def test_submodules_list_exists(self):
        from lys.apps.ai.modules import __submodules__
        assert isinstance(__submodules__, list)

    def test_submodules_contains_text_improvement(self):
        from lys.apps.ai.modules import __submodules__
        module_names = [m.__name__.split(".")[-1] if hasattr(m, "__name__") else str(m) for m in __submodules__]
        assert "text_improvement" in module_names

    def test_submodules_contains_conversation(self):
        from lys.apps.ai.modules import __submodules__
        module_names = [m.__name__.split(".")[-1] if hasattr(m, "__name__") else str(m) for m in __submodules__]
        assert "conversation" in module_names

    def test_submodules_contains_core(self):
        from lys.apps.ai.modules import __submodules__
        module_names = [m.__name__.split(".")[-1] if hasattr(m, "__name__") else str(m) for m in __submodules__]
        assert "core" in module_names
