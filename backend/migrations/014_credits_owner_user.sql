-- Migration 014: scope credits to users.
--
-- Credits move from a flat global library to a per-user library: each row
-- carries an optional ``owner_user_id`` (NULL = system/global credit visible
-- to every user, set = visible only to that user). Users can create their
-- own credits without colliding with names other users have already claimed.
--
-- Replaces the global UNIQUE on credits.credit_name with a composite unique
-- index on (owner_user_id, credit_name) so:
--   * system credits (NULL owner) compete for unique names amongst themselves
--   * each user competes for unique names within their own scope only
--
-- Idempotent. T-SQL conventions: GO on its own line is the batch separator;
-- DDL guarded with sys.* lookups so re-running is safe.

------------------------------------------------------------------------------
-- 1. Add owner_user_id column (nullable FK to users) + cascade-delete FK.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'credits') AND name = N'owner_user_id'
)
    ALTER TABLE credits ADD owner_user_id INT NULL;
GO

-- Check by column rather than constraint name: on a fresh DB, SQLAlchemy's
-- create_all emits a FK with its own auto-generated name, so a name lookup
-- would always miss and attempt to add a second FK on the same column.
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    INNER JOIN sys.columns c
        ON c.object_id = fkc.parent_object_id AND c.column_id = fkc.parent_column_id
    WHERE fk.parent_object_id = OBJECT_ID(N'credits')
      AND c.name = N'owner_user_id'
)
    ALTER TABLE credits ADD CONSTRAINT FK_credits_owner_user
        FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE;
GO

------------------------------------------------------------------------------
-- 2. Drop the auto-generated UNIQUE constraint on credit_name (if any).
--    SQLAlchemy emits this from ``unique=True`` on the column as either a
--    UQ key constraint or a unique index, depending on dialect/version.
--    Cover both forms.
------------------------------------------------------------------------------
DECLARE @uq_name SYSNAME = (
    SELECT TOP 1 kc.name
    FROM sys.key_constraints kc
    INNER JOIN sys.index_columns ic
        ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
    INNER JOIN sys.columns c
        ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE kc.parent_object_id = OBJECT_ID(N'credits')
      AND kc.type = 'UQ'
      AND c.name = N'credit_name'
);
IF @uq_name IS NOT NULL
    EXEC('ALTER TABLE credits DROP CONSTRAINT ' + @uq_name);
GO

DECLARE @idx_name SYSNAME = (
    SELECT TOP 1 i.name
    FROM sys.indexes i
    INNER JOIN sys.index_columns ic
        ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    INNER JOIN sys.columns c
        ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.object_id = OBJECT_ID(N'credits')
      AND i.is_unique = 1
      AND i.is_primary_key = 0
      AND i.is_unique_constraint = 0
      AND c.name = N'credit_name'
      AND i.name <> N'UX_credits_owner_name'
);
IF @idx_name IS NOT NULL
    EXEC('DROP INDEX ' + @idx_name + ' ON credits');
GO

------------------------------------------------------------------------------
-- 3. Replace with a composite unique index on (owner_user_id, credit_name).
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_credits_owner_name' AND object_id = OBJECT_ID(N'credits')
)
    CREATE UNIQUE INDEX UX_credits_owner_name
    ON credits (owner_user_id, credit_name);
GO
