"""
Constants for licensing emailing types.

These constants are used as EmailingType.id and must match the event type
constants in lys.apps.licensing.modules.event.consts for the unified event system.
"""

# License emailing types (aligned with event type constants)
LICENSE_GRANTED_EMAILING_TYPE = "LICENSE_GRANTED"
LICENSE_REVOKED_EMAILING_TYPE = "LICENSE_REVOKED"

# Subscription emailing types (aligned with event type constants)
SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE = "SUBSCRIPTION_PAYMENT_SUCCESS"
SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE = "SUBSCRIPTION_PAYMENT_FAILED"
SUBSCRIPTION_CANCELED_EMAILING_TYPE = "SUBSCRIPTION_CANCELED"