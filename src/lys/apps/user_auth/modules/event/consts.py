"""
Event type constants.

This module defines event type constants used across the application.
The actual channel configuration (email, notification, blocked) is defined
in EventService.get_channels() and can be overridden by subclasses.

Event type naming convention:
- Use SCREAMING_SNAKE_CASE
- The constant value is used as:
  - EmailingType.id (for email templates)
  - NotificationType.id (for notifications)
"""

# User lifecycle events (defined in lys.apps.user_auth)
USER_INVITED = "USER_INVITED"
USER_EMAIL_VERIFICATION_REQUESTED = "USER_EMAIL_VERIFICATION_REQUESTED"
USER_PASSWORD_RESET_REQUESTED = "USER_PASSWORD_RESET_REQUESTED"