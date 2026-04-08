-- Globalize statement credits: card_credits becomes a standardized library
-- (no card_id), and wallet_card_credits is the source of truth for which
-- credits a wallet card has.
DO $$
BEGIN
    -- Wipe all wallet-level credit selections (they referenced a (card, credit)
    -- pairing that no longer exists).
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'wallet_card_credits') THEN
        DELETE FROM wallet_card_credits;
    END IF;

    -- Drop wallet_card_credits.is_one_time (all remaining credits are recurring).
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'wallet_card_credits' AND column_name = 'is_one_time'
    ) THEN
        ALTER TABLE wallet_card_credits DROP COLUMN is_one_time;
    END IF;

    -- Keep only recurring rows in card_credits and dedupe by name.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_credits' AND column_name = 'is_one_time'
    ) THEN
        DELETE FROM card_credits WHERE is_one_time = TRUE;
    END IF;

    DELETE FROM card_credits
    WHERE id NOT IN (
        SELECT MIN(id) FROM card_credits GROUP BY credit_name
    );

    -- Drop the old (card_id, credit_name) unique constraint and the card_id FK.
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'card_credits_card_id_credit_name_key'
    ) THEN
        ALTER TABLE card_credits DROP CONSTRAINT card_credits_card_id_credit_name_key;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_credits' AND column_name = 'card_id'
    ) THEN
        ALTER TABLE card_credits DROP COLUMN card_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_credits' AND column_name = 'is_one_time'
    ) THEN
        ALTER TABLE card_credits DROP COLUMN is_one_time;
    END IF;

    -- Add unique on credit_name (matches the new ORM constraint).
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'card_credits_credit_name_key'
    ) THEN
        ALTER TABLE card_credits ADD CONSTRAINT card_credits_credit_name_key UNIQUE (credit_name);
    END IF;
END $$;
