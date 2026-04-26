-- Migration 015: add closed_date_clear flag to scenario_card_overlays.
--
-- Background: overlay.closed_date IS NULL has always meant "no override —
-- inherit closed_date from the underlying card_instance". That made it
-- impossible to express "force this owned card to be active in this
-- scenario" when the underlying instance has closed_date set: clearing
-- the overlay's closed_date just falls back to inheritance, so the modal
-- toggling Closed → Active in overlay mode appeared not to save.
--
-- Add a boolean flag the resolver checks AFTER three-tier resolution: when
-- True, effective.closed_date is forced to None regardless of what the
-- underlying instance has. The frontend sets it whenever the user picks
-- "Active" status in overlay mode.
--
-- Idempotent. Re-runnable.

------------------------------------------------------------------------------
-- 1. Add closed_date_clear to scenario_card_overlays.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'scenario_card_overlays')
      AND name = N'closed_date_clear'
)
    ALTER TABLE scenario_card_overlays
        ADD closed_date_clear BIT NOT NULL
            CONSTRAINT DF_scenario_card_overlays_closed_date_clear DEFAULT 0;
GO
