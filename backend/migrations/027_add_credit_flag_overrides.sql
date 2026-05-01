-- Per-instance overrides for `excludes_first_year` and `is_one_time` flags
-- on the credit-inheritance chain. Adds nullable columns to both
-- `wallet_card_credits` (middle tier) and `scenario_card_credits` (top
-- tier). NULL means "inherit from the previous tier" (matching the
-- existing `value` semantics where absence-of-row inherits, but here it's
-- column-level inheritance per row). Currency stays library-only by
-- design — only `value` and the two booleans are user-overridable.
--
-- Idempotent: every ALTER is guarded against re-add.

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'wallet_card_credits')
      AND name = 'excludes_first_year'
)
    ALTER TABLE wallet_card_credits ADD excludes_first_year BIT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'wallet_card_credits')
      AND name = 'is_one_time'
)
    ALTER TABLE wallet_card_credits ADD is_one_time BIT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'scenario_card_credits')
      AND name = 'excludes_first_year'
)
    ALTER TABLE scenario_card_credits ADD excludes_first_year BIT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'scenario_card_credits')
      AND name = 'is_one_time'
)
    ALTER TABLE scenario_card_credits ADD is_one_time BIT NULL;
GO
