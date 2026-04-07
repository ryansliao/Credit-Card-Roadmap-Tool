-- Phase 4c: per-wallet rotation overrides.
-- Lets the user pin specific (year, quarter) → category(s) on a wallet card,
-- bypassing the inferred historical activation probabilities for those quarters.
-- Used for confirmed quarters (e.g. Discover Calendar Choice picks, freshly
-- announced upcoming quarters) where the user knows the actual schedule.
DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS wallet_card_rotation_overrides (
        id                  SERIAL PRIMARY KEY,
        wallet_card_id      INTEGER NOT NULL REFERENCES wallet_cards(id) ON DELETE CASCADE,
        year                INTEGER NOT NULL,
        quarter             INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
        spend_category_id   INTEGER NOT NULL REFERENCES spend_categories(id) ON DELETE RESTRICT,
        UNIQUE (wallet_card_id, year, quarter, spend_category_id)
    );
    CREATE INDEX IF NOT EXISTS idx_wcro_wallet_card_id
        ON wallet_card_rotation_overrides(wallet_card_id);
END $$;
