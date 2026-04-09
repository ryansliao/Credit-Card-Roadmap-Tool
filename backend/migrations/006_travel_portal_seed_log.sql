-- Tracks which issuers / co-brands have been processed by the travel-portal
-- startup seed. Once an entry is logged here, the seed will skip it forever,
-- even if the user later deletes the corresponding TravelPortal.
--
-- Backfills rows for every issuer and co-brand that exists at the time of
-- this migration so the user's manual deletions stick after upgrade. New
-- issuers/co-brands added after this migration are not in the log, so they
-- still get auto-seeded once.
--
-- Wrapped in a single DO block because asyncpg can't run multi-statement
-- SQL through a prepared statement.

DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS travel_portal_seed_log (
        id        SERIAL PRIMARY KEY,
        kind      VARCHAR(20) NOT NULL,
        source_id INTEGER     NOT NULL,
        UNIQUE (kind, source_id)
    );

    INSERT INTO travel_portal_seed_log (kind, source_id)
    SELECT 'issuer', id FROM issuers
    ON CONFLICT (kind, source_id) DO NOTHING;

    INSERT INTO travel_portal_seed_log (kind, source_id)
    SELECT 'cobrand', id FROM co_brands
    ON CONFLICT (kind, source_id) DO NOTHING;
END $$;
