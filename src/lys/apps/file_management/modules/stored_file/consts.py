# Plugin configuration keys
FILE_STORAGE_PLUGIN_KEY = "file_storage"
FILE_STORAGE_BACKEND_KEY = "backend"
FILE_STORAGE_BUCKET_KEY = "bucket"
FILE_STORAGE_ACCESS_KEY_KEY = "access_key"
FILE_STORAGE_SECRET_KEY_KEY = "secret_key"
FILE_STORAGE_REGION_KEY = "region"
FILE_STORAGE_ENDPOINT_URL_KEY = "endpoint_url"

# Default presigned URL expiration (5 minutes)
DEFAULT_PRESIGNED_URL_EXPIRES = 300

# ZIP magic bytes (PK\x03\x04), for uploads that must be a ZIP archive. Only the local
# file header is accepted: an empty archive (PK\x05\x06) or a spanned one (PK\x07\x08)
# carries no document and is rejected.
ZIP_MAGIC_BYTES = b"PK\x03\x04"
