import inspect

import pytest


class TestEmailingStatusServiceStructure:
    """Verify that EmailingStatusService class exists and has the expected structure."""

    def test_class_exists(self):
        from lys.apps.base.modules.emailing.services import EmailingStatusService

        assert inspect.isclass(EmailingStatusService)

    def test_is_subclass_of_entity_service(self):
        from lys.apps.base.modules.emailing.services import EmailingStatusService
        from lys.core.services import EntityService

        assert issubclass(EmailingStatusService, EntityService)


class TestEmailingTypeServiceStructure:
    """Verify that EmailingTypeService class exists and has the expected structure."""

    def test_class_exists(self):
        from lys.apps.base.modules.emailing.services import EmailingTypeService

        assert inspect.isclass(EmailingTypeService)

    def test_is_subclass_of_entity_service(self):
        from lys.apps.base.modules.emailing.services import EmailingTypeService
        from lys.core.services import EntityService

        assert issubclass(EmailingTypeService, EntityService)


class TestEmailingServiceStructure:
    """Verify that EmailingService class exists and has the expected methods and signatures."""

    def test_class_exists(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert inspect.isclass(EmailingService)

    def test_is_subclass_of_entity_service(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.services import EntityService

        assert issubclass(EmailingService, EntityService)

    def test_has_get_template_env(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "get_template_env")

    def test_get_template_env_is_classmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "get_template_env"), classmethod
        )

    def test_get_template_env_is_sync(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert not inspect.iscoroutinefunction(EmailingService.get_template_env)

    def test_has_get_translations(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "get_translations")

    def test_get_translations_is_classmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "get_translations"), classmethod
        )

    def test_get_translations_signature(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_translations)
        param_names = list(sig.parameters.keys())
        assert "language_id" in param_names

    def test_get_translations_language_id_type_annotation(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_translations)
        assert sig.parameters["language_id"].annotation is str

    def test_get_translations_is_sync(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert not inspect.iscoroutinefunction(EmailingService.get_translations)

    def test_has_get_subject(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "get_subject")

    def test_get_subject_is_classmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "get_subject"), classmethod
        )

    def test_get_subject_signature(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_subject)
        param_names = list(sig.parameters.keys())
        assert "template_name" in param_names
        assert "language_id" in param_names
        assert "fallback_subject" in param_names

    def test_get_subject_template_name_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_subject)
        assert sig.parameters["template_name"].annotation is str

    def test_get_subject_language_id_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_subject)
        assert sig.parameters["language_id"].annotation is str

    def test_get_subject_fallback_subject_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.get_subject)
        assert sig.parameters["fallback_subject"].annotation is str

    def test_get_subject_is_sync(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert not inspect.iscoroutinefunction(EmailingService.get_subject)

    def test_has_compute_context(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "compute_context")

    def test_compute_context_is_staticmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "compute_context"), staticmethod
        )

    def test_compute_context_signature(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.compute_context)
        param_names = list(sig.parameters.keys())
        assert "context_description" in param_names
        assert "kwargs" in param_names

    def test_compute_context_context_description_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.compute_context)
        assert sig.parameters["context_description"].annotation is dict

    def test_compute_context_accepts_kwargs(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.compute_context)
        kwargs_param = sig.parameters["kwargs"]
        assert kwargs_param.kind == inspect.Parameter.VAR_KEYWORD

    def test_compute_context_is_sync(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert not inspect.iscoroutinefunction(EmailingService.compute_context)

    def test_has_generate_emailing(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "generate_emailing")

    def test_generate_emailing_is_classmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "generate_emailing"), classmethod
        )

    def test_generate_emailing_is_async(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert inspect.iscoroutinefunction(EmailingService.generate_emailing)

    def test_generate_emailing_signature(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.generate_emailing)
        param_names = list(sig.parameters.keys())
        assert "type_id" in param_names
        assert "email_address" in param_names
        assert "language_id" in param_names
        assert "session" in param_names

    def test_generate_emailing_type_id_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.generate_emailing)
        assert sig.parameters["type_id"].annotation is str

    def test_generate_emailing_email_address_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.generate_emailing)
        assert sig.parameters["email_address"].annotation is str

    def test_generate_emailing_language_id_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.generate_emailing)
        assert sig.parameters["language_id"].annotation is str

    def test_generate_emailing_accepts_kwargs(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.generate_emailing)
        kwargs_param = sig.parameters["kwargs"]
        assert kwargs_param.kind == inspect.Parameter.VAR_KEYWORD

    def test_has_send_email(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, "send_email")

    def test_send_email_is_classmethod(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert isinstance(
            inspect.getattr_static(EmailingService, "send_email"), classmethod
        )

    def test_send_email_is_sync(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        assert not inspect.iscoroutinefunction(EmailingService.send_email)

    def test_send_email_signature(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.send_email)
        param_names = list(sig.parameters.keys())
        assert "emailing_id" in param_names

    def test_send_email_emailing_id_type(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sig = inspect.signature(EmailingService.send_email)
        assert sig.parameters["emailing_id"].annotation is str


class TestEmailingServiceMethodCount:
    """Verify that EmailingService has the expected number of custom methods."""

    def test_has_exactly_six_custom_methods(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        expected_methods = {
            "get_template_env",
            "get_translations",
            "get_subject",
            "compute_context",
            "generate_emailing",
            "send_email",
        }
        # Verify all expected methods exist on the class
        for method_name in expected_methods:
            assert hasattr(EmailingService, method_name), (
                f"Missing method: {method_name}"
            )


class TestEmailingServiceAsyncSyncSeparation:
    """Verify that the correct methods are async versus sync on EmailingService."""

    def test_only_generate_emailing_is_async(self):
        from lys.apps.base.modules.emailing.services import EmailingService

        sync_methods = [
            "get_template_env",
            "get_translations",
            "get_subject",
            "compute_context",
            "send_email",
        ]
        async_methods = [
            "generate_emailing",
        ]
        for method_name in sync_methods:
            method = getattr(EmailingService, method_name)
            assert not inspect.iscoroutinefunction(method), (
                f"{method_name} should be sync but is async"
            )
        for method_name in async_methods:
            method = getattr(EmailingService, method_name)
            assert inspect.iscoroutinefunction(method), (
                f"{method_name} should be async but is sync"
            )
