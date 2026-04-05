DO $$
BEGIN
    -- Rename panel values: 'future' → 'on_deck', 'owned' → 'in_wallet'
    UPDATE wallet_cards SET panel = 'on_deck' WHERE panel = 'future';
    UPDATE wallet_cards SET panel = 'in_wallet' WHERE panel = 'owned';
    ALTER TABLE wallet_cards ALTER COLUMN panel SET DEFAULT 'on_deck';
END $$;
