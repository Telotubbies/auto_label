"""Column upgrades for identity, workspace and integration rows."""

API_KEYS = {"scopes": "JSON", "publishable": "BOOLEAN DEFAULT FALSE"}
CONNECTORS = {"last_sync": "FLOAT", "last_status": "VARCHAR(16) DEFAULT ''"}
USERS = {
    "email_verified": "FLOAT", "totp_secret": "VARCHAR(255)", "mfa_enabled": "BOOLEAN DEFAULT FALSE",
    "recovery_codes": "JSON", "totp_last_step": "INTEGER DEFAULT 0",
    "platform_admin": "BOOLEAN DEFAULT FALSE"}
WORKSPACES = {"require_mfa": "BOOLEAN DEFAULT FALSE",
              "data_region": "VARCHAR(16) DEFAULT 'th'",
              "quotas": "JSON"}
MEMBERS = {"custom_role_id": "VARCHAR(32)"}
PROJECT_MEMBERS = {"custom_role_id": "VARCHAR(32)"}
REFRESH_TOKENS = {
    "created": "FLOAT DEFAULT 0", "last_seen": "FLOAT DEFAULT 0",
    "ip": "VARCHAR(64) DEFAULT ''", "user_agent": "VARCHAR(255) DEFAULT ''"}
