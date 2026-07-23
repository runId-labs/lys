"""
Error codes for the legal app. Each is a (status_code, code) tuple, following the
lys error convention.
"""

# No legal document version is effective for the requested (type, language) pair.
LEGAL_VERSION_NOT_FOUND = (404, "LEGAL_VERSION_NOT_FOUND")

# A referenced legal document version id does not exist.
LEGAL_VERSION_ID_NOT_FOUND = (404, "LEGAL_VERSION_ID_NOT_FOUND")

# Authentication is required to record an acceptance.
LEGAL_AUTHENTICATION_REQUIRED = (401, "LEGAL_AUTHENTICATION_REQUIRED")

# The user has no resolvable email, so the proof's essential anchor cannot be captured.
LEGAL_ACCEPTANCE_EMAIL_REQUIRED = (422, "LEGAL_ACCEPTANCE_EMAIL_REQUIRED")

# Presigning the PDF failed (storage misconfiguration / credentials) — not a transient
# outage: presigning is offline, so a real storage outage surfaces downstream at the 302
# target, not here.
LEGAL_STORAGE_ERROR = (500, "LEGAL_STORAGE_ERROR")

# Could not assign a version number after repeated concurrent collisions at publish time
# (transient boot contention across replicas); retried on the next boot.
LEGAL_PUBLISH_CONTENTION = (503, "LEGAL_PUBLISH_CONTENTION")
