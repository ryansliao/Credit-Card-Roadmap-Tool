-- Make users.email optional. Local signup no longer requires an email; users
-- can register with just a username and password, and log in by either
-- identifier. SQL Server treats NULL as a single value in standard unique
-- constraints, which would block multiple email-less users, so we replace the
-- inline UNIQUE constraint with a filtered unique index that only enforces
-- uniqueness across non-NULL emails.

-- 1. Drop the auto-named UNIQUE constraint that SQLAlchemy emitted alongside
--    the column. Look it up dynamically because the name is system-generated.
DECLARE @uq_name NVARCHAR(255);
SELECT @uq_name = kc.name
FROM sys.key_constraints kc
INNER JOIN sys.index_columns ic
    ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
INNER JOIN sys.columns c
    ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE kc.parent_object_id = OBJECT_ID(N'users')
  AND kc.type = 'UQ'
  AND c.name = 'email';
IF @uq_name IS NOT NULL
    EXEC(N'ALTER TABLE users DROP CONSTRAINT ' + @uq_name);
GO

-- 2. Drop any non-constraint unique index on email (older deployments may have
--    one instead of a UQ constraint). Same dynamic lookup pattern.
DECLARE @ix_name NVARCHAR(255);
SELECT @ix_name = i.name
FROM sys.indexes i
INNER JOIN sys.index_columns ic
    ON i.object_id = ic.object_id AND i.index_id = ic.index_id
INNER JOIN sys.columns c
    ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID(N'users')
  AND i.is_unique = 1
  AND i.is_unique_constraint = 0
  AND i.is_primary_key = 0
  AND c.name = 'email'
  AND i.has_filter = 0;
IF @ix_name IS NOT NULL
    EXEC(N'DROP INDEX ' + @ix_name + N' ON users');
GO

-- 3. Make email nullable so registrations without an email can persist.
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'users')
      AND name = 'email'
      AND is_nullable = 0
)
BEGIN
    ALTER TABLE users ALTER COLUMN email NVARCHAR(255) NULL;
END
GO

-- 4. Re-add uniqueness for non-NULL emails via a filtered index. NULLs are
--    unrestricted; any provided email is still unique across all users.
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'users')
      AND name = 'UX_users_email_notnull'
)
BEGIN
    CREATE UNIQUE INDEX UX_users_email_notnull
        ON users(email)
        WHERE email IS NOT NULL;
END
GO
