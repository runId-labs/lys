SSO_PLUGIN_KEY = "sso"

# Redis key prefixes
SSO_STATE_PREFIX = "sso:state:"
SSO_SESSION_PREFIX = "sso:session:"

# SSO modes
SSO_MODE_LOGIN = "login"
SSO_MODE_SIGNUP = "signup"
SSO_MODE_LINK = "link"

VALID_SSO_MODES = {SSO_MODE_LOGIN, SSO_MODE_SIGNUP, SSO_MODE_LINK}

# TTLs (in seconds)
SSO_STATE_TTL = 600  # 10 minutes for OAuth state
SSO_SESSION_TTL = 900  # 15 minutes for signup session