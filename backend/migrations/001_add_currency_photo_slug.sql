-- Add photo_slug column to currencies table for displaying currency icons in the UI.
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'currencies')
      AND name = 'photo_slug'
)
BEGIN
    ALTER TABLE currencies
    ADD photo_slug NVARCHAR(120) NULL;
END
GO
