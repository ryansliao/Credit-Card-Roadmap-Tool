-- Migration 009: drop legacy wallet tables, columns, and duplicate wallet rows.
--
-- DESTRUCTIVE. Only run after migration 008 has been verified in production
-- and all client code uses the new /wallet + /scenarios surface. Reversal
-- requires restoring from backup — there is no down migration.
--
-- What 009 removes:
--   - Legacy override tables: wallet_card_credits, wallet_card_multipliers,
--     wallet_card_group_selections, wallet_card_category_priorities,
--     wallet_currency_cpp, wallet_portal_shares.
--   - Legacy ``wallet_cards`` table (its rows were copied to card_instances
--     in migration 008, preserving PK ids so override translations worked).
--   - Calc-config + cache columns on ``wallets`` (calc_*, include_subs,
--     last_calc_*) — all moved to ``scenarios`` in migration 008.
--   - Duplicate non-canonical wallet rows for users who previously had
--     multiple wallets. Their owned cards + per-wallet overrides were
--     re-pointed to the canonical wallet in 008; the canonical wallet is
--     the most-recently-updated row per user_id.
--   - The ``as_of_date`` column on wallets (no longer used in the new model).
--
-- What 009 adds:
--   - UNIQUE (user_id) on wallets (the one-wallet-per-user invariant).
--
-- T-SQL conventions: GO on its own line is the batch separator. Each
-- destructive step is guarded with ``IF EXISTS`` (or sys.* lookup) so the
-- migration is idempotent and re-runnable.

------------------------------------------------------------------------------
-- 1. Drop the four card-instance-keyed legacy override tables.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_card_category_priorities') AND type = 'U'
)
    DROP TABLE wallet_card_category_priorities;
GO

IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_card_group_selections') AND type = 'U'
)
    DROP TABLE wallet_card_group_selections;
GO

IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_card_multipliers') AND type = 'U'
)
    DROP TABLE wallet_card_multipliers;
GO

IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_card_credits') AND type = 'U'
)
    DROP TABLE wallet_card_credits;
GO

------------------------------------------------------------------------------
-- 2. Drop the wallet-wide override tables.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_currency_cpp') AND type = 'U'
)
    DROP TABLE wallet_currency_cpp;
GO

IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_portal_shares') AND type = 'U'
)
    DROP TABLE wallet_portal_shares;
GO

------------------------------------------------------------------------------
-- 3. Drop wallet_cards. Drop the explicit FK on pc_from_card_id first so
--    the table goes cleanly. The dependent override tables are already gone.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_wallet_cards_pc_from_card_id'
)
    ALTER TABLE wallet_cards DROP CONSTRAINT FK_wallet_cards_pc_from_card_id;
GO

IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_cards') AND type = 'U'
)
    DROP TABLE wallet_cards;
GO

------------------------------------------------------------------------------
-- 4. Drop calc-config + cache columns from wallets. Each requires dropping
--    its server-default first (default constraints have generated names —
--    look them up via sys.default_constraints).
------------------------------------------------------------------------------
DECLARE @drop_default_sql NVARCHAR(MAX);
DECLARE @col_name sysname;
DECLARE col_cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT c.name
    FROM sys.columns c
    WHERE c.object_id = OBJECT_ID(N'wallets')
      AND c.name IN (
          N'calc_start_date', N'calc_end_date',
          N'calc_duration_years', N'calc_duration_months',
          N'calc_window_mode', N'include_subs',
          N'last_calc_snapshot', N'last_calc_timestamp',
          N'as_of_date'
      );
OPEN col_cur;
FETCH NEXT FROM col_cur INTO @col_name;
WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE @df_name sysname;
    SELECT @df_name = dc.name
    FROM sys.default_constraints dc
    INNER JOIN sys.columns c
        ON c.default_object_id = dc.object_id
    WHERE c.object_id = OBJECT_ID(N'wallets')
      AND c.name = @col_name;
    IF @df_name IS NOT NULL
    BEGIN
        SET @drop_default_sql = N'ALTER TABLE wallets DROP CONSTRAINT [' + @df_name + N']';
        EXEC sp_executesql @drop_default_sql;
    END
    SET @drop_default_sql = N'ALTER TABLE wallets DROP COLUMN [' + @col_name + N']';
    EXEC sp_executesql @drop_default_sql;
    FETCH NEXT FROM col_cur INTO @col_name;
END
CLOSE col_cur;
DEALLOCATE col_cur;
GO

------------------------------------------------------------------------------
-- 5. Delete duplicate non-canonical wallet rows (one wallet per user).
--    Recompute the canonical set with the same rule migration 008 used:
--    most-recently-updated wallet per user_id wins.
------------------------------------------------------------------------------
IF OBJECT_ID(N'tempdb..#canonical_wallets_009') IS NOT NULL
    DROP TABLE #canonical_wallets_009;
SELECT user_id, canonical_wallet_id
INTO #canonical_wallets_009
FROM (
    SELECT
        user_id,
        id AS canonical_wallet_id,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC, id DESC) AS rn
    FROM wallets
) w
WHERE rn = 1;
GO

DELETE w
FROM wallets w
LEFT JOIN #canonical_wallets_009 cw
    ON cw.canonical_wallet_id = w.id
WHERE cw.canonical_wallet_id IS NULL;
GO

IF OBJECT_ID(N'tempdb..#canonical_wallets_009') IS NOT NULL
    DROP TABLE #canonical_wallets_009;
GO

------------------------------------------------------------------------------
-- 6. Add UNIQUE (user_id) on wallets — the one-wallet-per-user invariant.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.key_constraints kc
    WHERE kc.parent_object_id = OBJECT_ID(N'wallets')
      AND kc.type = 'UQ'
      AND kc.name = 'UQ_wallets_user_id'
)
    ALTER TABLE wallets
    ADD CONSTRAINT UQ_wallets_user_id UNIQUE (user_id);
GO
