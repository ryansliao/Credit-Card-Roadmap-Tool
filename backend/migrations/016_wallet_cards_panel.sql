DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'wallet_cards' AND column_name = 'panel'
    ) THEN
        ALTER TABLE wallet_cards ADD COLUMN panel VARCHAR(10) NOT NULL DEFAULT 'on_deck';

        -- Backfill: cards with added_date <= today and not closed → 'in_wallet'
        UPDATE wallet_cards
        SET panel = 'in_wallet'
        WHERE added_date <= CURRENT_DATE;

        -- Cards with added_date > today stay as 'on_deck' (the default)
    END IF;
END $$;
