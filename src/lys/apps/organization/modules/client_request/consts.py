"""Constants for the client_request module."""

# Statuses. Generic on purpose: every request is awaiting a decision, settled, dropped,
# or stuck. What made it stuck is carried by `reason_code`, not by a status of its own.
CLIENT_REQUEST_STATUS_PENDING = "PENDING"
CLIENT_REQUEST_STATUS_PROCESSED = "PROCESSED"
CLIENT_REQUEST_STATUS_CANCELLED = "CANCELLED"
CLIENT_REQUEST_STATUS_ERROR = "ERROR"

# Statuses a request can still move out of. Anything else is settled.
CLIENT_REQUEST_OPEN_STATUSES = (
    CLIENT_REQUEST_STATUS_PENDING,
    CLIENT_REQUEST_STATUS_ERROR,
)

# Reason code set when the requester's account is anonymized. The request is cancelled
# rather than kept: nobody is left to serve, and its free-text fields have been cleared.
CLIENT_REQUEST_REASON_REQUESTER_ANONYMIZED = "REQUESTER_ANONYMIZED"
