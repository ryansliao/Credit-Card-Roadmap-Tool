-- Add foreign key constraint on wallet_cards.pc_from_card_id → cards.id.
-- The column existed without a constraint, allowing dangling product-change
-- references.
--
-- ON DELETE NO ACTION (not CASCADE / SET NULL): SQL Server forbids two
-- cascading paths between the same pair of tables, and wallet_cards.card_id
-- already cascades from cards. NO ACTION means deleting a library card that
-- any wallet still references via pc_from_card_id is rejected at the FK
-- level. card_service.delete_card_if_unused enforces the same check at the
-- app layer so callers get a clean 409 instead of a raw SQL error.
--
-- First, null out any existing rows whose pc_from_card_id no longer points
-- to a real card so the FK creation does not fail on legacy bad data.
UPDATE wallet_cards
SET pc_from_card_id = NULL
WHERE pc_from_card_id IS NOT NULL
  AND pc_from_card_id NOT IN (SELECT id FROM cards);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_wallet_cards_pc_from_card_id'
)
BEGIN
    ALTER TABLE wallet_cards
    ADD CONSTRAINT FK_wallet_cards_pc_from_card_id
        FOREIGN KEY (pc_from_card_id)
        REFERENCES cards (id)
        ON DELETE NO ACTION;
END
GO
