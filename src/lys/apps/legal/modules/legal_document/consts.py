"""
Constants for the legal_document module.
"""

# Default, generic (English) document type codes. Product-facing labels
# (e.g. French "CGU"/"CGV") are the application's i18n concern, never stored here.
TERMS_OF_USE = "TERMS_OF_USE"
SALES_TERMS = "SALES_TERMS"
PRIVACY_POLICY = "PRIVACY_POLICY"

# Object-storage key prefix for immutable legal PDFs (storage concept).
STORAGE_KEY_PREFIX = "legal"

# Public URL / REST router prefix for legal documents (routing concept). Distinct from
# STORAGE_KEY_PREFIX even though they currently coincide — they answer different questions.
LEGAL_ROUTE_PREFIX = "legal"

# Plugin config key for the shared object-storage backend. Must match the key used by
# file_management (`file_storage`) so both apps resolve the same backend; declared locally
# to keep `legal` independent of `file_management`.
FILE_STORAGE_PLUGIN_KEY = "file_storage"

# Default lifetime of a presigned PDF URL (seconds).
DEFAULT_PRESIGNED_URL_EXPIRY = 300
