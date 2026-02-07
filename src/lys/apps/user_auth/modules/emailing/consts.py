"""
Constants for user authentication emailing types.

These constants are used as EmailingType.id and must match the event type
constants in lys.apps.user_auth.modules.event.consts for the unified event system.
"""

# User emailing types (aligned with event type constants)
USER_PASSWORD_RESET_EMAILING_TYPE = "USER_PASSWORD_RESET_REQUESTED"
USER_EMAIL_VERIFICATION_EMAILING_TYPE = "USER_EMAIL_VERIFICATION_REQUESTED"
USER_INVITATION_EMAILING_TYPE = "USER_INVITED"