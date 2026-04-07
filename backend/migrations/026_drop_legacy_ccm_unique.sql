-- Cleanup: ensure the legacy UNIQUE(card_id, category_id) constraint and any
-- equivalent legacy unique index on card_category_multipliers are gone.
--
-- Migration 024 attempted this but used a fragile LIKE pattern that didn't
-- always match the constraint definition string PostgreSQL returned. If 024
-- skipped the drop, the seed function fails to add Freedom Flex's standalone
-- additive premiums (Restaurants/Drug Stores collide with the rotating-group
-- rows under the legacy constraint), which silently rolls back the entire
-- Freedom Flex seed and leaves no portal-flagged Travel multiplier.
--
-- This migration walks pg_constraint and pg_index by column set instead, so
-- it always finds the right thing to drop. We cast attname to text because
-- pg_attribute.attname is the `name` type, which doesn't have a direct
-- equality operator with text[] literals.
DO $$
DECLARE
    cons RECORD;
BEGIN
    FOR cons IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class cls ON cls.oid = con.conrelid
        WHERE cls.relname = 'card_category_multipliers'
          AND con.contype = 'u'
          AND (
              SELECT array_agg(att.attname::text ORDER BY att.attname::text)
              FROM unnest(con.conkey) AS k
              JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k
          ) = ARRAY['card_id', 'category_id']::text[]
    LOOP
        RAISE NOTICE 'migration 026: dropping unique constraint %', cons.conname;
        EXECUTE 'ALTER TABLE card_category_multipliers DROP CONSTRAINT ' || quote_ident(cons.conname);
    END LOOP;

    FOR cons IN
        SELECT i.relname AS conname
        FROM pg_index x
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_class t ON t.oid = x.indrelid
        WHERE t.relname = 'card_category_multipliers'
          AND x.indisunique
          AND i.relname NOT IN ('uniq_ccm_standalone', 'uniq_ccm_grouped')
          AND (
              SELECT array_agg(att.attname::text ORDER BY att.attname::text)
              FROM unnest(x.indkey) AS k
              JOIN pg_attribute att ON att.attrelid = x.indrelid AND att.attnum = k
          ) = ARRAY['card_id', 'category_id']::text[]
          AND x.indpred IS NULL  -- skip the new partial indexes
    LOOP
        RAISE NOTICE 'migration 026: dropping unique index %', cons.conname;
        EXECUTE 'DROP INDEX ' || quote_ident(cons.conname);
    END LOOP;

    -- Re-assert the partial unique indexes in case migration 024 didn't get to them.
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_ccm_standalone
        ON card_category_multipliers(card_id, category_id)
        WHERE multiplier_group_id IS NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_ccm_grouped
        ON card_category_multipliers(card_id, category_id, multiplier_group_id)
        WHERE multiplier_group_id IS NOT NULL;
END $$;
