-- Remove the legacy "TakeOff15" Credit row. TakeOff15 is now modelled as the
-- card-level `takeoff15_enabled` flag (see migration 002), but the original
-- seed created a real Credit row plus card_credits links on Delta SkyMiles
-- Gold/Platinum/Reserve. The seed loader is upsert-only and does not clean up
-- entries that were removed from credits.yaml, so the orphan row persists and
-- keeps surfacing on Delta cards.
--
-- card_credits.credit_id and wallet_card_credits.library_credit_id both
-- cascade on delete, so this single statement cleans up every dependent row.
IF EXISTS (SELECT 1 FROM credits WHERE credit_name = 'TakeOff15')
BEGIN
    DELETE FROM credits WHERE credit_name = 'TakeOff15';
END
GO
