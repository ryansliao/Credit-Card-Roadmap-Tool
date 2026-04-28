-- Migration 019: indexes on hot scenario / wallet child-FK paths.
--
-- Cascading deletes on a wallet/scenario, and "where used" queries from
-- credits / overlays back to their parents, currently full-scan because no
-- index exists on the child FK columns. This migration adds the missing
-- indexes. All idempotent via sys.indexes lookups.

------------------------------------------------------------------------------
-- 1. scenario_card_overlays.scenario_id
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'scenario_card_overlays')
      AND name = N'IX_scenario_card_overlays_scenario_id'
)
    CREATE INDEX IX_scenario_card_overlays_scenario_id
        ON scenario_card_overlays (scenario_id);
GO

------------------------------------------------------------------------------
-- 2. scenario_card_credits.library_credit_id (reverse "which scenarios
--    override this credit?" lookup)
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'scenario_card_credits')
      AND name = N'IX_scenario_card_credits_library_credit'
)
    CREATE INDEX IX_scenario_card_credits_library_credit
        ON scenario_card_credits (library_credit_id);
GO

------------------------------------------------------------------------------
-- 3. wallet_card_credits.card_instance_id (cascade-delete + per-instance
--    fetch)
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'wallet_card_credits')
      AND name = N'IX_wallet_card_credits_card_instance_id'
)
    CREATE INDEX IX_wallet_card_credits_card_instance_id
        ON wallet_card_credits (card_instance_id);
GO

------------------------------------------------------------------------------
-- 4. wallet_card_credits.library_credit_id (reverse "which instances
--    override this credit?" lookup)
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'wallet_card_credits')
      AND name = N'IX_wallet_card_credits_library_credit'
)
    CREATE INDEX IX_wallet_card_credits_library_credit
        ON wallet_card_credits (library_credit_id);
GO
