"""
Emailing services for user_role app.

Provides EmailingTypeService for the extended EmailingType with roles,
and EmailingBatchService with role-based recipient resolution.
"""
from lys.apps.base.modules.emailing.services import (
    EmailingBatchService as BaseEmailingBatchService,
    EmailingTypeService as BaseEmailingTypeService,
)
from lys.apps.user_role.mixins.recipient_resolution import RoleRecipientResolutionMixin
from lys.core.registries import register_service


@register_service()
class EmailingTypeService(BaseEmailingTypeService):
    """
    Service for managing emailing types with roles relationship.

    Inherits from base EmailingTypeService. Entity resolution uses
    app_manager.get_entity("emailing_type") which returns the extended
    EmailingType with roles (last-registered-wins).
    """
    pass


@register_service()
class EmailingBatchService(RoleRecipientResolutionMixin, BaseEmailingBatchService):
    """
    Extended EmailingBatchService with role-based recipient resolution.

    Role-based resolution is provided by RoleRecipientResolutionMixin which
    adds users with roles linked to the EmailingType (via user_role table).

    No method override needed — the mixin's _resolve_recipients() and
    _resolve_recipients_sync() are used automatically via MRO.
    """
    pass