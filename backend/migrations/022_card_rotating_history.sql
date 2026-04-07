-- Phase 2: rotating-category card support.
-- Adds an `is_rotating` flag to multiplier groups and creates a history table
-- of (card, year, quarter, category) rows that the calculator averages into
-- per-category activation probabilities.
DO $$
BEGIN
    ALTER TABLE card_multiplier_groups
        ADD COLUMN IF NOT EXISTS is_rotating BOOLEAN NOT NULL DEFAULT FALSE;

    CREATE TABLE IF NOT EXISTS card_rotating_history (
        id                  SERIAL PRIMARY KEY,
        card_id             INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
        year                INTEGER NOT NULL,
        quarter             INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
        spend_category_id   INTEGER NOT NULL REFERENCES spend_categories(id) ON DELETE RESTRICT,
        UNIQUE (card_id, year, quarter, spend_category_id)
    );

    CREATE INDEX IF NOT EXISTS idx_card_rotating_history_card_id
        ON card_rotating_history(card_id);
END $$;
