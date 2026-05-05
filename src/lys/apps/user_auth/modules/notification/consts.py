"""
Constants for the notification module.

Defines the canonical severity ids referenced by NotificationType.severity_id
and loaded as fixtures into notification_severity. Use these constants
everywhere a severity id is needed instead of hard-coded strings.
"""

NOTIFICATION_SEVERITY_INFO = "INFO"
NOTIFICATION_SEVERITY_SUCCESS = "SUCCESS"
NOTIFICATION_SEVERITY_WARNING = "WARNING"
NOTIFICATION_SEVERITY_ERROR = "ERROR"