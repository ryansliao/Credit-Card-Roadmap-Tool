-- Drop redundant `updated_at` AFTER UPDATE triggers on tables where the
-- ORM model already sets `updated_at` via `onupdate=func.now()`. The
-- triggers were created out-of-band and aren't tracked in any earlier
-- migration; they duplicate the ORM-managed update default and break
-- SQL Server's `OUTPUT inserted.<col>` clause that SQLAlchemy emits for
-- `eager_defaults=True`, surfacing as 500s on UPDATEs (first observed on
-- PATCH /api/credits/{id}).
--
-- Idempotent: each DROP is guarded by `IF EXISTS`, so this is safe to
-- run on environments where the triggers were never created.

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_credits_updated_at')
    DROP TRIGGER trg_credits_updated_at;
GO

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_cards_updated_at')
    DROP TRIGGER trg_cards_updated_at;
GO

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_wallets_updated_at')
    DROP TRIGGER trg_wallets_updated_at;
GO

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_wallet_spend_items_updated_at')
    DROP TRIGGER trg_wallet_spend_items_updated_at;
GO

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_card_category_multipliers_updated_at')
    DROP TRIGGER trg_card_category_multipliers_updated_at;
GO

IF EXISTS (SELECT 1 FROM sys.triggers WHERE name = 'trg_issuer_application_rules_updated_at')
    DROP TRIGGER trg_issuer_application_rules_updated_at;
GO
