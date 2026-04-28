-- Migration 018: add users.is_admin to gate /admin/* reference-data routers.
--
-- Until now every /admin/* endpoint was unauthenticated. The router-level
-- ``require_admin_user`` dependency now reads this flag; existing users
-- default to non-admin and the column is flipped manually via direct DB
-- access (no UI). Idempotent.

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'users')
      AND name = N'is_admin'
)
BEGIN
    ALTER TABLE users ADD is_admin BIT NOT NULL CONSTRAINT DF_users_is_admin DEFAULT 0;
END
GO
