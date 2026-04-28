-- Migration 020: drop cards.takeoff15_enabled.
--
-- Background: ``takeoff15_enabled`` (Delta TakeOff 15: 15% award discount on
-- Delta SkyMiles cards) was added in migration 002 and the credit was removed
-- in migration 006. The CPP-boost branch in calculator_data_service has been
-- removed; the column has no remaining readers. Drop the column. Idempotent.

------------------------------------------------------------------------------
-- 1. Drop the default constraint first (SQL Server requires this before
--    dropping a column with a DEFAULT). Look up dynamically — the constraint
--    name is system-generated.
------------------------------------------------------------------------------
DECLARE @df_name NVARCHAR(255);
SELECT @df_name = dc.name
FROM sys.default_constraints dc
INNER JOIN sys.columns c
    ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
WHERE dc.parent_object_id = OBJECT_ID(N'cards')
  AND c.name = N'takeoff15_enabled';
IF @df_name IS NOT NULL
    EXEC(N'ALTER TABLE cards DROP CONSTRAINT ' + @df_name);
GO

------------------------------------------------------------------------------
-- 2. Drop the column itself.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'cards')
      AND name = N'takeoff15_enabled'
)
    ALTER TABLE cards DROP COLUMN takeoff15_enabled;
GO
