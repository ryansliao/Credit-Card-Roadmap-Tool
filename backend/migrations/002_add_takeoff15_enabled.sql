-- Add takeoff15_enabled column to cards table.
-- When true, the card's SkyMiles CPP is boosted by 1/(1-0.15) to model the
-- 15% award redemption discount on Delta flights.
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'cards')
      AND name = 'takeoff15_enabled'
)
BEGIN
    ALTER TABLE cards
    ADD takeoff15_enabled BIT NOT NULL DEFAULT 0;
END
GO
