-- Migration 008: introduce Scenarios + CardInstance unification.
--
-- Refactors the wallet model from many-wallets-per-user to one-wallet-per-user
-- with multiple Scenarios per Wallet. Owned cards and future cards collapse
-- into a single ``card_instances`` table where ``scenario_id IS NULL`` means
-- owned and ``scenario_id`` set means a future card scoped to that scenario.
--
-- This migration is ADDITIVE. Legacy tables (wallet_cards, wallet_card_credits,
-- wallet_card_multipliers, wallet_card_group_selections, wallet_card_category_priorities,
-- wallet_currency_cpp, wallet_portal_shares) and the calc-config columns on
-- wallets are LEFT IN PLACE so old code keeps compiling. Migration 009 drops
-- them once the new path is verified.
--
-- Idempotent. Re-running is safe — every CREATE / INSERT is guarded.
--
-- T-SQL conventions: GO on its own line is the batch separator. CREATE TRIGGER
-- / CREATE PROCEDURE must be the first statement in a batch (not used here).
-- All DDL is guarded via sys.objects / sys.columns / sys.indexes /
-- sys.key_constraints lookups.

------------------------------------------------------------------------------
-- 1. Create scenarios table
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenarios') AND type = 'U'
)
BEGIN
    CREATE TABLE scenarios (
        id                  INT             IDENTITY(1,1) PRIMARY KEY,
        wallet_id           INT             NOT NULL,
        name                NVARCHAR(120)   NOT NULL,
        description         NVARCHAR(MAX)   NULL,
        is_default          BIT             NOT NULL CONSTRAINT DF_scenarios_is_default DEFAULT 0,
        start_date          DATE            NULL,
        end_date            DATE            NULL,
        duration_years      INT             NOT NULL CONSTRAINT DF_scenarios_duration_years DEFAULT 2,
        duration_months     INT             NOT NULL CONSTRAINT DF_scenarios_duration_months DEFAULT 0,
        window_mode         NVARCHAR(20)    NOT NULL CONSTRAINT DF_scenarios_window_mode DEFAULT 'duration',
        include_subs        BIT             NOT NULL CONSTRAINT DF_scenarios_include_subs DEFAULT 1,
        last_calc_snapshot  NVARCHAR(MAX)   NULL,
        last_calc_timestamp DATETIMEOFFSET(7) NULL,
        created_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenarios_created_at DEFAULT SYSUTCDATETIME(),
        updated_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenarios_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_scenarios_wallet
            FOREIGN KEY (wallet_id) REFERENCES wallets (id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_scenarios_wallet_id' AND object_id = OBJECT_ID(N'scenarios')
)
BEGIN
    CREATE INDEX IX_scenarios_wallet_id ON scenarios (wallet_id);
END
GO

-- Filtered unique index: at most one default scenario per wallet
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UX_scenarios_default_per_wallet' AND object_id = OBJECT_ID(N'scenarios')
)
BEGIN
    CREATE UNIQUE INDEX UX_scenarios_default_per_wallet
    ON scenarios (wallet_id)
    WHERE is_default = 1;
END
GO

------------------------------------------------------------------------------
-- 2. Create card_instances table (replaces wallet_cards)
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'card_instances') AND type = 'U'
)
BEGIN
    CREATE TABLE card_instances (
        id                          INT             IDENTITY(1,1) PRIMARY KEY,
        wallet_id                   INT             NOT NULL,
        scenario_id                 INT             NULL,
        card_id                     INT             NOT NULL,
        opening_date                DATE            NOT NULL,
        product_change_date         DATE            NULL,
        closed_date                 DATE            NULL,
        sub_earned_date             DATE            NULL,
        sub_projected_earn_date     DATE            NULL,
        pc_from_instance_id         INT             NULL,
        sub_points                  INT             NULL,
        sub_min_spend               INT             NULL,
        sub_months                  INT             NULL,
        sub_spend_earn              INT             NULL,
        years_counted               INT             NOT NULL CONSTRAINT DF_card_instances_years_counted DEFAULT 2,
        annual_bonus                INT             NULL,
        annual_bonus_percent        FLOAT           NULL,
        annual_bonus_first_year_only BIT            NULL,
        annual_fee                  FLOAT           NULL,
        first_year_fee              FLOAT           NULL,
        secondary_currency_rate     FLOAT           NULL,
        panel                       NVARCHAR(16)    NOT NULL CONSTRAINT DF_card_instances_panel DEFAULT 'considering',
        is_enabled                  BIT             NOT NULL CONSTRAINT DF_card_instances_is_enabled DEFAULT 1,
        created_at                  DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_card_instances_created_at DEFAULT SYSUTCDATETIME(),
        updated_at                  DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_card_instances_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_card_instances_wallet
            FOREIGN KEY (wallet_id) REFERENCES wallets (id) ON DELETE CASCADE,
        CONSTRAINT FK_card_instances_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE NO ACTION,
        CONSTRAINT FK_card_instances_card
            FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE,
        CONSTRAINT FK_card_instances_pc_from_instance
            FOREIGN KEY (pc_from_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_card_instances_wallet_scenario' AND object_id = OBJECT_ID(N'card_instances')
)
BEGIN
    CREATE INDEX IX_card_instances_wallet_scenario
    ON card_instances (wallet_id, scenario_id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_card_instances_wallet_scenario_enabled' AND object_id = OBJECT_ID(N'card_instances')
)
BEGIN
    CREATE INDEX IX_card_instances_wallet_scenario_enabled
    ON card_instances (wallet_id, scenario_id, is_enabled);
END
GO

------------------------------------------------------------------------------
-- 3. Create scenario_card_overlays
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_card_overlays') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_card_overlays (
        id                          INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id                 INT             NOT NULL,
        card_instance_id            INT             NOT NULL,
        closed_date                 DATE            NULL,
        product_change_date         DATE            NULL,
        sub_earned_date             DATE            NULL,
        sub_projected_earn_date     DATE            NULL,
        sub_points                  INT             NULL,
        sub_min_spend               INT             NULL,
        sub_months                  INT             NULL,
        sub_spend_earn              INT             NULL,
        annual_bonus                INT             NULL,
        annual_bonus_percent        FLOAT           NULL,
        annual_bonus_first_year_only BIT            NULL,
        annual_fee                  FLOAT           NULL,
        first_year_fee              FLOAT           NULL,
        secondary_currency_rate     FLOAT           NULL,
        is_enabled                  BIT             NULL,
        created_at                  DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_overlays_created_at DEFAULT SYSUTCDATETIME(),
        updated_at                  DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_overlays_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_scenario_card_overlays UNIQUE (scenario_id, card_instance_id),
        CONSTRAINT FK_scenario_card_overlays_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_card_overlays_instance
            FOREIGN KEY (card_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION
    );
END
GO

------------------------------------------------------------------------------
-- 4. Create scenario_card_multipliers
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_card_multipliers') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_card_multipliers (
        id                  INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id         INT             NOT NULL,
        card_instance_id    INT             NOT NULL,
        category_id         INT             NOT NULL,
        multiplier          FLOAT           NOT NULL,
        created_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_multipliers_created_at DEFAULT SYSUTCDATETIME(),
        updated_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_multipliers_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_scenario_card_multipliers UNIQUE (scenario_id, card_instance_id, category_id),
        CONSTRAINT FK_scenario_card_multipliers_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_card_multipliers_instance
            FOREIGN KEY (card_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION,
        CONSTRAINT FK_scenario_card_multipliers_category
            FOREIGN KEY (category_id) REFERENCES spend_categories (id) ON DELETE NO ACTION
    );
END
GO

------------------------------------------------------------------------------
-- 5. Create scenario_card_credits
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_card_credits') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_card_credits (
        id                  INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id         INT             NOT NULL,
        card_instance_id    INT             NOT NULL,
        library_credit_id   INT             NOT NULL,
        value               FLOAT           NOT NULL,
        created_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_credits_created_at DEFAULT SYSUTCDATETIME(),
        updated_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_card_credits_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_scenario_card_credits UNIQUE (scenario_id, card_instance_id, library_credit_id),
        CONSTRAINT FK_scenario_card_credits_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_card_credits_instance
            FOREIGN KEY (card_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION,
        CONSTRAINT FK_scenario_card_credits_credit
            FOREIGN KEY (library_credit_id) REFERENCES credits (id) ON DELETE NO ACTION
    );
END
GO

------------------------------------------------------------------------------
-- 6. Create scenario_card_category_priorities
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_card_category_priorities') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_card_category_priorities (
        id                  INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id         INT             NOT NULL,
        card_instance_id    INT             NOT NULL,
        spend_category_id   INT             NOT NULL,
        CONSTRAINT UQ_scenario_card_category_priorities UNIQUE (scenario_id, spend_category_id),
        CONSTRAINT FK_scenario_card_category_priorities_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_card_category_priorities_instance
            FOREIGN KEY (card_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION,
        CONSTRAINT FK_scenario_card_category_priorities_category
            FOREIGN KEY (spend_category_id) REFERENCES spend_categories (id) ON DELETE NO ACTION
    );
END
GO

------------------------------------------------------------------------------
-- 7. Create scenario_card_group_selections
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_card_group_selections') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_card_group_selections (
        id                      INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id             INT             NOT NULL,
        card_instance_id        INT             NOT NULL,
        multiplier_group_id     INT             NOT NULL,
        spend_category_id       INT             NOT NULL,
        CONSTRAINT UQ_scenario_card_group_selections UNIQUE (scenario_id, card_instance_id, multiplier_group_id, spend_category_id),
        CONSTRAINT FK_scenario_card_group_selections_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_card_group_selections_instance
            FOREIGN KEY (card_instance_id) REFERENCES card_instances (id) ON DELETE NO ACTION,
        CONSTRAINT FK_scenario_card_group_selections_group
            FOREIGN KEY (multiplier_group_id) REFERENCES card_multiplier_groups (id) ON DELETE NO ACTION,
        CONSTRAINT FK_scenario_card_group_selections_category
            FOREIGN KEY (spend_category_id) REFERENCES spend_categories (id) ON DELETE NO ACTION
    );
END
GO

------------------------------------------------------------------------------
-- 8. Create scenario_currency_cpp
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_currency_cpp') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_currency_cpp (
        id              INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id     INT             NOT NULL,
        currency_id     INT             NOT NULL,
        cents_per_point FLOAT           NOT NULL,
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_currency_cpp_created_at DEFAULT SYSUTCDATETIME(),
        updated_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_currency_cpp_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_scenario_currency_cpp UNIQUE (scenario_id, currency_id),
        CONSTRAINT FK_scenario_currency_cpp_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_currency_cpp_currency
            FOREIGN KEY (currency_id) REFERENCES currencies (id) ON DELETE CASCADE
    );
END
GO

------------------------------------------------------------------------------
-- 9. Create scenario_currency_balances (new — no legacy data to copy)
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_currency_balances') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_currency_balances (
        id              INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id     INT             NOT NULL,
        currency_id     INT             NOT NULL,
        balance         FLOAT           NOT NULL CONSTRAINT DF_scenario_currency_balances_balance DEFAULT 0,
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_currency_balances_created_at DEFAULT SYSUTCDATETIME(),
        updated_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_scenario_currency_balances_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_scenario_currency_balances UNIQUE (scenario_id, currency_id),
        CONSTRAINT FK_scenario_currency_balances_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_currency_balances_currency
            FOREIGN KEY (currency_id) REFERENCES currencies (id) ON DELETE CASCADE
    );
END
GO

------------------------------------------------------------------------------
-- 10. Create scenario_portal_shares
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'scenario_portal_shares') AND type = 'U'
)
BEGIN
    CREATE TABLE scenario_portal_shares (
        id                  INT             IDENTITY(1,1) PRIMARY KEY,
        scenario_id         INT             NOT NULL,
        travel_portal_id    INT             NOT NULL,
        share               FLOAT           NOT NULL,
        CONSTRAINT UQ_scenario_portal_shares UNIQUE (scenario_id, travel_portal_id),
        CONSTRAINT FK_scenario_portal_shares_scenario
            FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE,
        CONSTRAINT FK_scenario_portal_shares_portal
            FOREIGN KEY (travel_portal_id) REFERENCES travel_portals (id) ON DELETE CASCADE
    );
END
GO

------------------------------------------------------------------------------
-- 11. Drop the legacy unique constraint on (wallet_id, card_id) so duplicates
--     of the same library card can coexist in a wallet (multi-application
--     cards, post-migration product-change chains).
------------------------------------------------------------------------------
DECLARE @uq_name sysname;
SELECT @uq_name = kc.name
FROM sys.key_constraints kc
INNER JOIN sys.indexes i
    ON i.object_id = kc.parent_object_id
   AND i.index_id = kc.unique_index_id
INNER JOIN sys.index_columns ic
    ON ic.object_id = i.object_id
   AND ic.index_id = i.index_id
INNER JOIN sys.columns c
    ON c.object_id = ic.object_id
   AND c.column_id = ic.column_id
WHERE kc.parent_object_id = OBJECT_ID(N'wallet_cards')
  AND kc.type = 'UQ'
  AND c.name IN (N'wallet_id', N'card_id')
GROUP BY kc.name
HAVING COUNT(DISTINCT c.name) = 2;

IF @uq_name IS NOT NULL
    EXEC('ALTER TABLE wallet_cards DROP CONSTRAINT ' + QUOTENAME(@uq_name));
GO

------------------------------------------------------------------------------
-- 12. Backfill: pick a canonical wallet per user (most recently updated).
------------------------------------------------------------------------------
IF OBJECT_ID(N'tempdb..#canonical_wallets') IS NOT NULL DROP TABLE #canonical_wallets;
SELECT user_id, canonical_wallet_id
INTO #canonical_wallets
FROM (
    SELECT
        user_id,
        id AS canonical_wallet_id,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC, id DESC) AS rn
    FROM wallets
) w
WHERE rn = 1;
GO

------------------------------------------------------------------------------
-- 13. Spawn one Scenario per existing Wallet (canonical or not). The scenario
--     spawned from the canonical wallet becomes is_default = 1 for that
--     wallet; non-canonical wallets become non-default named scenarios under
--     the canonical wallet. Skip wallets whose scenario was already created
--     by a prior run.
------------------------------------------------------------------------------
IF OBJECT_ID(N'tempdb..#wallet_to_scenario') IS NOT NULL DROP TABLE #wallet_to_scenario;
CREATE TABLE #wallet_to_scenario (
    old_wallet_id INT NOT NULL,
    canonical_wallet_id INT NOT NULL,
    scenario_id INT NOT NULL
);
GO

-- Insert default scenarios for canonical wallets that don't already have one.
INSERT INTO scenarios (
    wallet_id, name, description, is_default,
    start_date, end_date, duration_years, duration_months, window_mode,
    include_subs, last_calc_snapshot, last_calc_timestamp
)
OUTPUT inserted.wallet_id, inserted.wallet_id, inserted.id
INTO #wallet_to_scenario (old_wallet_id, canonical_wallet_id, scenario_id)
SELECT
    w.id,
    ISNULL(w.name, 'Default'),
    w.description,
    1,
    w.calc_start_date,
    w.calc_end_date,
    ISNULL(w.calc_duration_years, 2),
    ISNULL(w.calc_duration_months, 0),
    ISNULL(w.calc_window_mode, 'duration'),
    ISNULL(w.include_subs, 1),
    w.last_calc_snapshot,
    w.last_calc_timestamp
FROM wallets w
INNER JOIN #canonical_wallets cw ON cw.canonical_wallet_id = w.id
LEFT JOIN scenarios s ON s.wallet_id = w.id AND s.is_default = 1
WHERE s.id IS NULL;
GO

-- Insert non-default scenarios for non-canonical wallets, parented to the
-- canonical wallet. Each preserves its original name so the user can still
-- recognise it as a separate iteration.
INSERT INTO scenarios (
    wallet_id, name, description, is_default,
    start_date, end_date, duration_years, duration_months, window_mode,
    include_subs, last_calc_snapshot, last_calc_timestamp
)
OUTPUT inserted.wallet_id, inserted.wallet_id, inserted.id
INTO #wallet_to_scenario (old_wallet_id, canonical_wallet_id, scenario_id)
SELECT
    cw.canonical_wallet_id,
    ISNULL(w.name, 'Scenario'),
    w.description,
    0,
    w.calc_start_date,
    w.calc_end_date,
    ISNULL(w.calc_duration_years, 2),
    ISNULL(w.calc_duration_months, 0),
    ISNULL(w.calc_window_mode, 'duration'),
    ISNULL(w.include_subs, 1),
    w.last_calc_snapshot,
    w.last_calc_timestamp
FROM wallets w
INNER JOIN #canonical_wallets cw ON cw.user_id = w.user_id
LEFT JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = w.id
WHERE w.id <> cw.canonical_wallet_id
  AND w2s.scenario_id IS NULL;
GO

-- Patch #wallet_to_scenario rows that came from the first INSERT — those used
-- the canonical's own wallet_id as old_wallet_id, but the OUTPUT couldn't
-- distinguish "canonical-as-source" from a plain join. Make sure every
-- canonical wallet has a row keyed under its own ID (it's the source for its
-- own owned cards and overrides).
UPDATE w2s
SET canonical_wallet_id = cw.canonical_wallet_id
FROM #wallet_to_scenario w2s
INNER JOIN #canonical_wallets cw ON cw.user_id = (
    SELECT user_id FROM wallets WHERE id = w2s.old_wallet_id
);
GO

------------------------------------------------------------------------------
-- 14. Backfill card_instances from wallet_cards.
--     Preserve PK ids (IDENTITY_INSERT) so legacy override rows keyed by
--     wallet_card_id translate cleanly to card_instance_id in the next step.
--     Translation rules:
--       - wallet_id  -> the canonical wallet for that user
--       - scenario_id -> NULL when added_date <= today (owned),
--                        else #wallet_to_scenario(old_wallet_id).scenario_id
--                        (future card pinned to the originating wallet's scenario)
--       - opening_date -> walk pc_from_card_id chain to root (acquisition_type='opened').
--                         Falls back to own added_date if chain breaks or origin missing.
--       - product_change_date -> own added_date when acquisition_type='product_change',
--                                else NULL
--     pc_from_instance_id is resolved in the next batch (needs the new ids).
------------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM card_instances)
BEGIN
    SET IDENTITY_INSERT card_instances ON;

    ;WITH chain AS (
        -- Anchor: every wallet_card knows its own wallet_id, card_id, added_date,
        -- and the library card it was changed FROM.
        SELECT
            wc.id                          AS wc_id,
            wc.wallet_id,
            wc.card_id,
            wc.acquisition_type,
            wc.pc_from_card_id,
            wc.added_date,
            wc.added_date                  AS root_added_date,
            wc.acquisition_type            AS root_acq_type,
            0                              AS depth
        FROM wallet_cards wc

        UNION ALL

        -- Walk back through pc chain: find any wallet_card in the same wallet
        -- whose card_id matches the current row's pc_from_card_id, with the
        -- latest added_date that is still <= the current row's added_date.
        -- Recursive CTE returns one parent per child, so the chain is a path.
        SELECT
            c.wc_id,
            c.wallet_id,
            c.card_id,
            c.acquisition_type,
            parent.pc_from_card_id,
            c.added_date,
            parent.added_date              AS root_added_date,
            parent.acquisition_type        AS root_acq_type,
            c.depth + 1                    AS depth
        FROM chain c
        CROSS APPLY (
            SELECT TOP 1 p.added_date, p.acquisition_type, p.pc_from_card_id
            FROM wallet_cards p
            WHERE p.wallet_id = c.wallet_id
              AND p.card_id   = c.pc_from_card_id
              AND p.added_date <= c.added_date
            ORDER BY p.added_date DESC, p.id DESC
        ) parent
        WHERE c.acquisition_type = 'product_change'
          AND c.pc_from_card_id IS NOT NULL
          AND c.depth < 10  -- safety against cycles
    ),
    roots AS (
        SELECT
            wc_id,
            -- Pick the deepest reached row in the chain — that's the closest
            -- known root. If the row never recurses, depth=0 and root_*
            -- equals the row's own added_date / acquisition_type.
            root_added_date,
            root_acq_type,
            ROW_NUMBER() OVER (PARTITION BY wc_id ORDER BY depth DESC) AS rn
        FROM chain
    )
    INSERT INTO card_instances (
        id, wallet_id, scenario_id, card_id,
        opening_date, product_change_date, closed_date,
        sub_earned_date, sub_projected_earn_date,
        sub_points, sub_min_spend, sub_months, sub_spend_earn,
        years_counted, annual_bonus, annual_bonus_percent, annual_bonus_first_year_only,
        annual_fee, first_year_fee, secondary_currency_rate,
        panel, is_enabled, created_at, updated_at
    )
    SELECT
        wc.id,
        cw.canonical_wallet_id,
        CASE
            WHEN wc.added_date <= CAST(SYSUTCDATETIME() AS DATE) THEN NULL
            ELSE w2s.scenario_id
        END,
        wc.card_id,
        ISNULL(r.root_added_date, wc.added_date),
        CASE WHEN wc.acquisition_type = 'product_change' THEN wc.added_date ELSE NULL END,
        wc.closed_date,
        wc.sub_earned_date,
        wc.sub_projected_earn_date,
        wc.sub_points, wc.sub_min_spend, wc.sub_months, wc.sub_spend_earn,
        ISNULL(wc.years_counted, 2),
        wc.annual_bonus, wc.annual_bonus_percent, wc.annual_bonus_first_year_only,
        wc.annual_fee, wc.first_year_fee, wc.secondary_currency_rate,
        wc.panel, wc.is_enabled, wc.created_at, wc.updated_at
    FROM wallet_cards wc
    INNER JOIN #canonical_wallets cw ON cw.user_id = (
        SELECT user_id FROM wallets WHERE id = wc.wallet_id
    )
    INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wc.wallet_id
    LEFT JOIN roots r ON r.wc_id = wc.id AND r.rn = 1;

    SET IDENTITY_INSERT card_instances OFF;
END
GO

------------------------------------------------------------------------------
-- 15. Resolve pc_from_instance_id by translating each row's legacy
--     pc_from_card_id into the matching card_instance.id for that wallet.
--     Only set when the chain link is unambiguous (single matching instance
--     in the same canonical wallet whose opening_date <= this row's
--     product_change_date).
------------------------------------------------------------------------------
UPDATE ci
SET pc_from_instance_id = src.src_id
FROM card_instances ci
CROSS APPLY (
    SELECT TOP 1 src.id AS src_id
    FROM card_instances src
    INNER JOIN wallet_cards wc_self ON wc_self.id = ci.id
    WHERE src.wallet_id = ci.wallet_id
      AND wc_self.pc_from_card_id IS NOT NULL
      AND src.card_id = wc_self.pc_from_card_id
      AND src.id <> ci.id
      AND (ci.product_change_date IS NULL OR src.opening_date <= ci.product_change_date)
    ORDER BY src.opening_date DESC, src.id DESC
) src
WHERE ci.product_change_date IS NOT NULL
  AND ci.pc_from_instance_id IS NULL;
GO

------------------------------------------------------------------------------
-- 16. Backfill scenario_card_multipliers from wallet_card_multipliers.
--     wallet_card_multipliers is keyed by (wallet_id, card_id) — translate
--     to a card_instance via the matching wallet_card.id (preserved as
--     card_instance.id in step 14).
------------------------------------------------------------------------------
INSERT INTO scenario_card_multipliers (scenario_id, card_instance_id, category_id, multiplier, created_at, updated_at)
SELECT DISTINCT
    w2s.scenario_id,
    wc.id,
    wcm.category_id,
    wcm.multiplier,
    wcm.created_at,
    wcm.updated_at
FROM wallet_card_multipliers wcm
INNER JOIN wallet_cards wc
    ON wc.wallet_id = wcm.wallet_id
   AND wc.card_id   = wcm.card_id
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wcm.wallet_id
LEFT JOIN scenario_card_multipliers existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.card_instance_id = wc.id
   AND existing.category_id = wcm.category_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 17. Backfill scenario_card_credits from wallet_card_credits.
------------------------------------------------------------------------------
INSERT INTO scenario_card_credits (scenario_id, card_instance_id, library_credit_id, value, created_at, updated_at)
SELECT
    w2s.scenario_id,
    wcc.wallet_card_id,
    wcc.library_credit_id,
    wcc.value,
    wcc.created_at,
    wcc.updated_at
FROM wallet_card_credits wcc
INNER JOIN wallet_cards wc ON wc.id = wcc.wallet_card_id
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wc.wallet_id
LEFT JOIN scenario_card_credits existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.card_instance_id = wcc.wallet_card_id
   AND existing.library_credit_id = wcc.library_credit_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 18. Backfill scenario_card_category_priorities from
--     wallet_card_category_priorities.
------------------------------------------------------------------------------
INSERT INTO scenario_card_category_priorities (scenario_id, card_instance_id, spend_category_id)
SELECT
    w2s.scenario_id,
    wccp.wallet_card_id,
    wccp.spend_category_id
FROM wallet_card_category_priorities wccp
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wccp.wallet_id
LEFT JOIN scenario_card_category_priorities existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.spend_category_id = wccp.spend_category_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 19. Backfill scenario_card_group_selections from
--     wallet_card_group_selections.
------------------------------------------------------------------------------
INSERT INTO scenario_card_group_selections (scenario_id, card_instance_id, multiplier_group_id, spend_category_id)
SELECT
    w2s.scenario_id,
    wcgs.wallet_card_id,
    wcgs.multiplier_group_id,
    wcgs.spend_category_id
FROM wallet_card_group_selections wcgs
INNER JOIN wallet_cards wc ON wc.id = wcgs.wallet_card_id
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wc.wallet_id
LEFT JOIN scenario_card_group_selections existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.card_instance_id = wcgs.wallet_card_id
   AND existing.multiplier_group_id = wcgs.multiplier_group_id
   AND existing.spend_category_id = wcgs.spend_category_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 20. Backfill scenario_currency_cpp from wallet_currency_cpp.
------------------------------------------------------------------------------
INSERT INTO scenario_currency_cpp (scenario_id, currency_id, cents_per_point, created_at, updated_at)
SELECT
    w2s.scenario_id,
    wcc.currency_id,
    wcc.cents_per_point,
    wcc.created_at,
    wcc.updated_at
FROM wallet_currency_cpp wcc
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wcc.wallet_id
LEFT JOIN scenario_currency_cpp existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.currency_id = wcc.currency_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 21. Backfill scenario_portal_shares from wallet_portal_shares.
------------------------------------------------------------------------------
INSERT INTO scenario_portal_shares (scenario_id, travel_portal_id, share)
SELECT
    w2s.scenario_id,
    wps.travel_portal_id,
    wps.share
FROM wallet_portal_shares wps
INNER JOIN #wallet_to_scenario w2s ON w2s.old_wallet_id = wps.wallet_id
LEFT JOIN scenario_portal_shares existing
    ON existing.scenario_id = w2s.scenario_id
   AND existing.travel_portal_id = wps.travel_portal_id
WHERE existing.id IS NULL;
GO

------------------------------------------------------------------------------
-- 22. Merge wallet_spend_items into the canonical wallet.
--     Rule (b) from design: prefer canonical's existing row; fill in
--     non-canonical values only when canonical is 0.0 (treat zero as unset).
------------------------------------------------------------------------------
-- Step 1: insert any non-canonical (user_spend_category_id) that the
-- canonical wallet doesn't have a row for.
INSERT INTO wallet_spend_items (wallet_id, user_spend_category_id, amount, created_at, updated_at)
SELECT
    cw.canonical_wallet_id,
    src.user_spend_category_id,
    src.amount,
    src.created_at,
    src.updated_at
FROM wallet_spend_items src
INNER JOIN #canonical_wallets cw ON cw.user_id = (
    SELECT user_id FROM wallets WHERE id = src.wallet_id
)
LEFT JOIN wallet_spend_items dst
    ON dst.wallet_id = cw.canonical_wallet_id
   AND dst.user_spend_category_id = src.user_spend_category_id
WHERE src.wallet_id <> cw.canonical_wallet_id
  AND dst.id IS NULL;
GO

-- Step 2: where canonical's row is 0, take the max non-zero value from any
-- non-canonical wallet for the same category.
UPDATE dst
SET amount = src.amount, updated_at = SYSUTCDATETIME()
FROM wallet_spend_items dst
INNER JOIN #canonical_wallets cw ON cw.canonical_wallet_id = dst.wallet_id
CROSS APPLY (
    SELECT TOP 1 si.amount
    FROM wallet_spend_items si
    INNER JOIN wallets w ON w.id = si.wallet_id
    WHERE w.user_id = cw.user_id
      AND si.wallet_id <> cw.canonical_wallet_id
      AND si.user_spend_category_id = dst.user_spend_category_id
      AND si.amount > 0
    ORDER BY si.amount DESC, si.id DESC
) src
WHERE dst.amount = 0;
GO

------------------------------------------------------------------------------
-- 23. Move foreign_spend_percent onto the canonical wallet — pick the most
--     recently updated wallet's value among the user's wallets.
------------------------------------------------------------------------------
UPDATE w
SET foreign_spend_percent = src.foreign_spend_percent
FROM wallets w
INNER JOIN #canonical_wallets cw ON cw.canonical_wallet_id = w.id
CROSS APPLY (
    SELECT TOP 1 src.foreign_spend_percent
    FROM wallets src
    WHERE src.user_id = cw.user_id
    ORDER BY src.updated_at DESC, src.id DESC
) src
WHERE w.foreign_spend_percent = 0
  AND src.foreign_spend_percent <> 0;
GO

------------------------------------------------------------------------------
-- Cleanup temp tables
------------------------------------------------------------------------------
IF OBJECT_ID(N'tempdb..#canonical_wallets') IS NOT NULL DROP TABLE #canonical_wallets;
IF OBJECT_ID(N'tempdb..#wallet_to_scenario') IS NOT NULL DROP TABLE #wallet_to_scenario;
GO
