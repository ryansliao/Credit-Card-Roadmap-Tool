-- Migration 016: add wallet_card_credits table.
--
-- Background: ScenarioCardCredit stores per-scenario per-instance credit
-- valuations (the legacy WalletCardCredit was folded into it in 008/009).
-- That left no place for owned cards to carry "my actual valuation" of a
-- credit at the wallet level — the WalletTab modal had nowhere to persist
-- credit edits, and scenarios had no wallet-level baseline to inherit from.
--
-- This adds wallet_card_credits as the wallet-level override layer:
--
--     library CardCredit  →  wallet_card_credits  →  ScenarioCardCredit
--     (issuer-stated)        (user's wallet edit)    (per-scenario hypothesis)
--
-- For owned cards (scenario_id IS NULL) the WalletTab modal writes here.
-- ScenarioResolver merges library defaults with wallet overrides and then
-- with scenario overrides per-scenario. Future cards skip the wallet layer.
--
-- Idempotent. Re-runnable.

------------------------------------------------------------------------------
-- 1. Create wallet_card_credits.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_card_credits') AND type = 'U'
)
    CREATE TABLE wallet_card_credits (
        id                INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        card_instance_id  INT NOT NULL,
        library_credit_id INT NOT NULL,
        value             FLOAT NOT NULL,
        created_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_card_credits_created_at
                              DEFAULT SYSUTCDATETIME(),
        updated_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_card_credits_updated_at
                              DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_wallet_card_credits_card_instance
            FOREIGN KEY (card_instance_id)
            REFERENCES card_instances(id)
            ON DELETE CASCADE,
        CONSTRAINT FK_wallet_card_credits_credit
            FOREIGN KEY (library_credit_id)
            REFERENCES credits(id),
        CONSTRAINT UX_wallet_card_credits_instance_credit
            UNIQUE (card_instance_id, library_credit_id)
    );
GO
