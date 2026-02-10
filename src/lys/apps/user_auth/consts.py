"""
Authentication and authorization constants.

This module defines the constants used throughout the authentication system
to maintain consistency in permission levels, access types, and error codes.
These constants are used in fixtures, permissions, and business logic.
"""

AUTH_PLUGIN_KEY = "auth"
AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY = "check_xsrf_token"

# Key used in permission dictionaries for owner-type access
OWNER_ACCESS_KEY = "owner"

# secured cookie key
ACCESS_COOKIE_KEY = "access_token"
REFRESH_COOKIE_KEY = "refresh_token"
XSRF_COOKIE_KEY = "XSRF-TOKEN"

# request header key
REQUEST_HEADER_XSRF_TOKEN_KEY = 'x-xsrf-token'


