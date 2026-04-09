-- Create travel_portals reference table and travel_portal_cards join, and
-- repoint wallet_portal_shares from per-issuer to per-travel-portal.
--
-- The previous schema keyed wallet_portal_shares by issuer_id (with the
-- assumption that "Chase issues this card, so a Chase share applies to it").
-- We're replacing that implicit issuer→portal tie with an explicit
-- TravelPortal entity that owns the list of cards eligible for its
-- portal-only multipliers.
--
-- Existing wallet_portal_shares rows can't be migrated cleanly (we don't
-- know which travel portal an issuer maps to), so we drop them. The user
-- can re-create the shares against the new TravelPortal entries.

DO $$
DECLARE
    sch text := current_schema();
    has_old_col boolean;
    has_new_col boolean;
    uniq_name text;
BEGIN
    -- 1. travel_portals table.
    CREATE TABLE IF NOT EXISTS travel_portals (
        id   SERIAL PRIMARY KEY,
        name VARCHAR(120) NOT NULL UNIQUE
    );

    -- 2. travel_portal_cards join table.
    CREATE TABLE IF NOT EXISTS travel_portal_cards (
        travel_portal_id INTEGER NOT NULL
            REFERENCES travel_portals(id) ON DELETE CASCADE,
        card_id INTEGER NOT NULL
            REFERENCES cards(id) ON DELETE CASCADE,
        PRIMARY KEY (travel_portal_id, card_id)
    );

    -- 3. wallet_portal_shares: swap issuer_id for travel_portal_id.
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = sch
          AND table_name = 'wallet_portal_shares'
          AND column_name = 'issuer_id'
    ) INTO has_old_col;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = sch
          AND table_name = 'wallet_portal_shares'
          AND column_name = 'travel_portal_id'
    ) INTO has_new_col;

    IF has_old_col AND NOT has_new_col THEN
        -- Drop existing rows: no clean issuer→portal mapping exists.
        DELETE FROM wallet_portal_shares;

        -- Drop the old unique constraint (auto-named, so locate it).
        SELECT conname INTO uniq_name
        FROM pg_constraint
        WHERE conrelid = 'wallet_portal_shares'::regclass
          AND contype = 'u'
        LIMIT 1;
        IF uniq_name IS NOT NULL THEN
            EXECUTE 'ALTER TABLE wallet_portal_shares DROP CONSTRAINT ' || quote_ident(uniq_name);
        END IF;

        ALTER TABLE wallet_portal_shares DROP COLUMN issuer_id;
        ALTER TABLE wallet_portal_shares
            ADD COLUMN travel_portal_id INTEGER NOT NULL
            REFERENCES travel_portals(id) ON DELETE CASCADE;
        ALTER TABLE wallet_portal_shares
            ADD CONSTRAINT wallet_portal_shares_wallet_portal_uniq
            UNIQUE (wallet_id, travel_portal_id);
    END IF;
END $$;
