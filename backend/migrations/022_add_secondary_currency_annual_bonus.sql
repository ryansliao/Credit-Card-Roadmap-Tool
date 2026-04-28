-- Migration 022: add secondary_currency_annual_bonus column to cards.
--
-- Stores a recurring annual bonus paid in the card's secondary currency
-- (e.g. Bilt Palladium awards 200 Bilt Cash/yr). Flows through
-- apply_bilt_2_housing_mode's BC budget so it can fund Tier 1 housing
-- unlock or Point Accelerator activations alongside BC earned from spend.
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'cards')
      AND name = 'secondary_currency_annual_bonus'
)
BEGIN
    ALTER TABLE cards
    ADD secondary_currency_annual_bonus INT NULL;
END
GO
