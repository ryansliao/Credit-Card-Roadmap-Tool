-- Migration 017: add last_calc_input_hash to scenarios.
--
-- Background: the roadmap previously live-computed each owned/future
-- card's projected SUB earn date from a wallet-wide daily spend rate on
-- every GET /scenarios/{id}/roadmap. The calc endpoint, in contrast,
-- derives projected dates from an allocation-aware per-card daily rate
-- (plan_sub_targeting + calc_annual_allocated_spend). The two paths
-- could disagree, and roadmap dates would shift on every fetch
-- regardless of whether the user had run the calc.
--
-- We now tie projected dates to the calculate button: the calc snapshot
-- carries per-instance projected dates, and the roadmap reads them from
-- that snapshot. To detect when the snapshot is stale relative to the
-- current scenario state (start_date edit, spend change, instance
-- added/closed, overlay tweak, override change, etc.), we hash the full
-- ComputeInputs + scenario calc config at calc time and persist the
-- hash. Roadmap recomputes the hash and only consumes the snapshot when
-- the hashes match; otherwise it falls back to the empty-state semantics
-- (no projected date, no countdown).
--
-- Idempotent. Re-runnable.

------------------------------------------------------------------------------
-- 1. Add last_calc_input_hash column.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'scenarios')
      AND name = N'last_calc_input_hash'
)
    ALTER TABLE scenarios ADD last_calc_input_hash NVARCHAR(64) NULL;
GO
