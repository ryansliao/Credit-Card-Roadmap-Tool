-- Migration 023: add housing_type column to wallets.
--
-- Lets a user pick whether their housing spend hits Rent or Mortgage so the
-- "Housing" UserSpendCategory maps 100% to one earn category instead of
-- splitting 50/50 across both. Stored as 'rent' or 'mortgage'; NULL falls
-- back to 'rent' (the most common case).
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'wallets')
      AND name = 'housing_type'
)
BEGIN
    ALTER TABLE wallets
    ADD housing_type NVARCHAR(16) NULL;
END
GO
