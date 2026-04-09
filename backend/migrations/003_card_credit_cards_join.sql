-- Replace the card_credits.card_ids INTEGER[] column with a proper many-to-many
-- join table. The array column was awkward to edit in DB GUIs (DBeaver/pgAdmin)
-- and did not enforce foreign-key integrity against the cards table.

CREATE TABLE IF NOT EXISTS card_credit_cards (
    credit_id INTEGER NOT NULL REFERENCES card_credits(id) ON DELETE CASCADE,
    card_id   INTEGER NOT NULL REFERENCES cards(id)        ON DELETE CASCADE,
    PRIMARY KEY (credit_id, card_id)
);

CREATE INDEX IF NOT EXISTS ix_card_credit_cards_card_id
    ON card_credit_cards (card_id);

-- Copy any data already populated in the legacy card_ids array column over to
-- the join table. Skip card IDs that don't exist in the cards table so the FK
-- doesn't blow up on stale references.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'card_credits' AND column_name = 'card_ids'
    ) THEN
        INSERT INTO card_credit_cards (credit_id, card_id)
        SELECT cc.id, cid
          FROM card_credits cc,
               LATERAL unnest(cc.card_ids) AS cid
         WHERE cc.card_ids IS NOT NULL
           AND array_length(cc.card_ids, 1) > 0
           AND EXISTS (SELECT 1 FROM cards WHERE cards.id = cid)
        ON CONFLICT DO NOTHING;

        ALTER TABLE card_credits DROP COLUMN card_ids;
    END IF;
END $$;
