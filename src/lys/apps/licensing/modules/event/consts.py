"""
Event type constants for licensing.

These constants are used as:
- EmailingType.id (for email templates)
- NotificationType.id (for notifications)
"""

# License lifecycle events
LICENSE_GRANTED = "LICENSE_GRANTED"
LICENSE_REVOKED = "LICENSE_REVOKED"

# Subscription payment events
SUBSCRIPTION_PAYMENT_SUCCESS = "SUBSCRIPTION_PAYMENT_SUCCESS"
SUBSCRIPTION_PAYMENT_FAILED = "SUBSCRIPTION_PAYMENT_FAILED"
SUBSCRIPTION_CANCELED = "SUBSCRIPTION_CANCELED"