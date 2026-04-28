-- Migration 021: drop sub_earned_date from card_instances and
-- scenario_card_overlays.
--
-- Background: per CLAUDE.md, this column was preserved post-refactor for
-- compatibility but had no current readers in either the calculator or the
-- roadmap. Audit confirmed nothing reads or projects it; the projected SUB
-- earn date now flows entirely through CardData.sub_projected_earn_date /
-- CardResult.sub_projected_earn_date / RoadmapCardStatus.
-- Drop the column from both tables. Idempotent.

------------------------------------------------------------------------------
-- 1. Drop sub_earned_date from card_instances.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'card_instances')
      AND name = N'sub_earned_date'
)
    ALTER TABLE card_instances DROP COLUMN sub_earned_date;
GO

------------------------------------------------------------------------------
-- 2. Drop sub_earned_date from scenario_card_overlays.
------------------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'scenario_card_overlays')
      AND name = N'sub_earned_date'
)
    ALTER TABLE scenario_card_overlays DROP COLUMN sub_earned_date;
GO
