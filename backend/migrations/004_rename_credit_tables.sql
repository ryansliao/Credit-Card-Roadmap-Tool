-- Rename the global credit library and the join table:
--   card_credits      -> credits        (the global credit library)
--   card_credit_cards -> card_credits   (join table linking credits to cards)
--
-- PostgreSQL FK constraints are stored by OID, so they automatically follow
-- table renames. Existing references in wallet_card_credits.library_credit_id
-- and the join table's credit_id column continue to point at the right table
-- without needing to be rewritten.
--
-- The migration runs after Base.metadata.create_all on every startup. On a
-- pre-rename DB, create_all will (because the model now declares the new
-- tablenames) try to create an empty 'credits' table alongside the existing
-- 'card_credits' library. Detect and drop that empty stub before renaming.

DO $$
DECLARE
    sch text := current_schema();
    has_join_old   boolean;
    has_credits    boolean;
    credits_empty  boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'card_credit_cards'
    ) INTO has_join_old;

    -- Nothing to do if we're already on the post-rename schema (or fresh DB).
    IF NOT has_join_old THEN
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'credits'
    ) INTO has_credits;

    IF has_credits THEN
        EXECUTE 'SELECT NOT EXISTS (SELECT 1 FROM credits LIMIT 1)' INTO credits_empty;
        IF credits_empty THEN
            DROP TABLE credits;
        ELSE
            RAISE EXCEPTION
                'Cannot rename card_credits -> credits: a non-empty credits table already exists';
        END IF;
    END IF;

    ALTER TABLE card_credits      RENAME TO credits;
    ALTER TABLE card_credit_cards RENAME TO card_credits;
END $$;
