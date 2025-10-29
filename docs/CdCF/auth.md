# Authentication System

## Overview

The authentication system provides secure user authentication with JWT tokens, refresh token management, and progressive rate limiting to prevent brute force attacks.

## Authentication Flow

### Login Process

1. **User submits credentials**
   - Login identifier (email)
   - Password

2. **System validates**
   - User existence
   - Account status (enabled/disabled)
   - Rate limiting status
   - Password correctness

3. **System generates tokens**
   - Refresh token (long-lived, stored in database)
   - Access token (short-lived, JWT)
   - XSRF token (cross-site request forgery protection)

4. **System sets cookies**
   - Refresh token cookie (path: `/auth`)
   - Access token cookie (path: `/graphql`)

### Token Refresh Flow

1. **Client sends request with cookies**
   - Refresh token from cookie

2. **System validates refresh token**
   - Token exists in database
   - Token not revoked
   - Token not expired (connection timeout)
   - Token not expired (once-use timeout, if enabled)
   - Token not already used (if single-use mode enabled)

3. **System generates new access token**
   - New JWT access token
   - New XSRF token
   - Optionally: new refresh token (if single-use mode)

4. **System updates cookies**
   - New access token cookie
   - New refresh token cookie (if rotated)

### Logout Process

1. **Client requests logout**
   - Sends refresh token from cookie

2. **System revokes tokens**
   - Marks all user refresh tokens as revoked
   - Sets `revoked_at` timestamp

3. **System clears cookies**
   - Deletes refresh token cookie
   - Deletes access token cookie

## Token Types

### Refresh Token

**Purpose**: Long-lived token for session persistence

**Properties**:
- Stored in database
- UUID identifier
- Linked to specific user
- Cookie-based transmission

**Expiration conditions**:
- Connection timeout reached (default: 24 hours)
- Token explicitly revoked
- Once-use timeout reached (optional)
- Token already used (if single-use mode)

**Security features**:
- HttpOnly cookie (prevents JavaScript access)
- Secure flag (HTTPS only in production)
- SameSite=Lax (CSRF protection)
- Path restricted to `/auth`

### Access Token

**Purpose**: Short-lived token for API authorization

**Properties**:
- JWT format (signed, not encrypted)
- Contains user claims (id, super_user status)
- Includes expiration timestamp
- Includes XSRF token
- Cookie-based transmission

**Lifetime**:
- Default: 5 minutes
- Must be refreshed via refresh token

**Security features**:
- HttpOnly cookie
- Secure flag (HTTPS only in production)
- SameSite=Lax
- Path restricted to `/graphql`
- Signed with secret key (prevents tampering)

### XSRF Token

**Purpose**: Cross-site request forgery protection

**Properties**:
- Random 64-byte hex string
- Included in access token JWT claims
- Returned to client in response

**Usage**:
- Client must include in request headers
- Server validates against JWT claim
- Optional (can be disabled in settings)

## Login Attempt Tracking

### Purpose

- Track authentication attempts per user
- Implement progressive rate limiting
- Maintain security audit trail
- Detect potential attacks

### Tracking Logic

**Failed attempt after success**:
- Create new record
- Status: `failed`
- Attempt count: `1`

**Failed attempt after failed**:
- Update existing record
- Increment attempt count
- Maintain same status

**Successful attempt (any prior status)**:
- Create new record
- Status: `success`
- Attempt count: `1`

### Data Retention

**Complete history preserved**:
- No deletion of login attempt records
- Each record represents a "session" of attempts
- Failed sessions show total failed attempts
- Success sessions show individual logins

**Benefits**:
- Full audit trail
- Attack pattern detection
- User behavior analysis
- Compliance reporting

### Record Structure

Each login attempt record contains:
- User identifier
- Status (success/failed)
- Attempt count (accumulated for failed, always 1 for success)
- Created timestamp (start of session)
- Updated timestamp (last attempt)
- Blocked until timestamp (if rate limited)

## Rate Limiting

### Progressive Lockout Strategy

**Purpose**: Prevent brute force attacks while minimizing user friction

**Thresholds** (configurable):
- 3 failed attempts → 60 seconds lockout
- 5 failed attempts → 900 seconds (15 minutes) lockout

**How it works**:
1. Counter increments with each failed attempt
2. System checks attempt count against thresholds
3. Highest matching threshold determines lockout duration
4. User blocked until timeout expires
5. Counter continues incrementing if attempts persist during lockout

**Lockout behavior**:
- User receives error with remaining time
- Countdown displayed to user
- After timeout expires, counter remains (no reset)
- Successful login resets progression (new record created)

### Rate Limit Bypass

**Disabled entirely**:
- Configuration flag: `login_rate_limit_enabled = False`
- No lockouts applied
- Attempts still tracked for audit

**Account permanently blocked**:
- User status set to disabled
- Immediate block, no rate limit check
- Requires manual intervention to re-enable

## User Status Management

### Status Types

**Enabled**:
- Can authenticate
- Rate limiting applies
- Normal operation

**Disabled**:
- Cannot authenticate
- Immediate rejection (before password check)
- No login attempt recorded
- Manual re-enable required

### Status Transitions

**Enable → Disable**:
- User locked out
- Existing sessions can continue (until token expiry)
- New logins rejected

**Disable → Enable**:
- User can authenticate again
- Previous login attempt history maintained
- Rate limiting applies from current state

## Security Features

### Password Security

**Storage**:
- bcrypt hashing
- Salted automatically
- No plaintext storage

**Validation**:
- Timing-safe comparison
- No password hints
- Failed attempts counted equally (user exists vs wrong password)

### Token Security

**Refresh tokens**:
- Cryptographically random UUID
- Database storage (not client-controlled)
- Revocable (logout, security event)
- Session isolation (revoke all user tokens)

**Access tokens**:
- JWT signature validation
- Expiration enforcement
- User claims validation
- XSRF token binding

**Cookie security**:
- HttpOnly (XSS protection)
- Secure flag in production (HTTPS only)
- SameSite=Lax (CSRF protection)
- Domain restriction
- Path restriction

### Attack Mitigation

**Brute force attacks**:
- Progressive rate limiting
- Attempt tracking
- Account lockout
- No distinction between invalid user vs wrong password

**Session hijacking**:
- Short-lived access tokens
- Refresh token rotation (optional)
- Revocation mechanism
- Secure cookie flags

**CSRF attacks**:
- XSRF token validation
- SameSite cookie attribute
- Origin validation (optional)

**Timing attacks**:
- Constant-time password comparison (bcrypt)
- Same response time for invalid user vs wrong password

## Configuration Options

### Token Expiration

- `access_token_expire_minutes`: Access token lifetime (default: 5)
- `connection_expire_minutes`: Refresh token max lifetime (default: 1440 = 24h)
- `once_refresh_token_expire_minutes`: Single-use refresh token timeout (optional)

### Rate Limiting

- `login_rate_limit_enabled`: Enable/disable rate limiting (default: true)
- `login_lockout_durations`: Threshold → duration mapping (default: {3: 60, 5: 900})

### Token Behavior

- `refresh_token_used_once`: Single-use refresh tokens (default: false)
- `cookie_secure`: HTTPS-only cookies (default: true in production)
- `cookie_http_only`: Prevent JavaScript access (default: true)
- `cookie_same_site`: CSRF protection level (default: "Lax")

### XSRF Protection

- `xsrf_token_enabled`: Enable XSRF validation (default: configurable per environment)

## API Endpoints

### GraphQL Mutations

**login**:
- Input: login (email), password
- Output: user info, access token expiry, XSRF token
- Sets: refresh token cookie, access token cookie
- Public access (no authentication required)

**refresh_access_token**:
- Input: refresh token (from cookie)
- Output: user info, new access token expiry, new XSRF token
- Sets: new access token cookie, optionally new refresh token cookie
- Public access (uses refresh token for auth)

**logout**:
- Input: refresh token (from cookie)
- Output: success status
- Clears: all cookies, revokes refresh token
- Public access (uses refresh token for auth)

## Audit & Monitoring

### Login Attempt History

**Tracking data**:
- User identifier
- Timestamp
- Success/failure status
- Attempt count in session
- Lockout duration (if applied)
- IP address (optional, application-level)

**Use cases**:
- Security audits
- Compliance reporting
- Attack detection
- User behavior analysis
- Support troubleshooting

### Logged Events

**Successful login**:
- User identifier
- Timestamp
- Log level: INFO

**Failed login**:
- User identifier
- Attempt number
- Lockout duration (if any)
- Timestamp
- Log level: WARNING

**Rate limit triggered**:
- User identifier
- Remaining lockout time
- Attempt count
- Timestamp
- Log level: WARNING

**Account blocked**:
- User identifier
- Timestamp
- Log level: WARNING

## Best Practices

### For Developers

**Token handling**:
- Never log token values
- Use environment variables for secrets
- Rotate secret keys periodically
- Validate all JWT claims

**Rate limiting**:
- Configure thresholds per environment
- Monitor lockout frequency
- Adjust based on attack patterns
- Consider IP-based rate limiting (future)

**Password management**:
- Enforce strong password policies (application level)
- Never log passwords
- Use bcrypt work factor appropriate for hardware
- Consider password age/rotation policies (future)

### For Users

**Account security**:
- Use strong, unique passwords
- Log out when done
- Report suspicious activity
- Change password if compromise suspected

**Lockout handling**:
- Wait for timeout to expire
- Do not retry repeatedly (extends lockout)
- Contact support if locked out repeatedly
- Verify correct credentials before retrying