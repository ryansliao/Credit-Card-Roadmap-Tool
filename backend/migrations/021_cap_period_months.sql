-- Replace cap_period string with cap_period_months integer on both
-- card_multiplier_groups and card_category_multipliers.
-- monthly=1, quarterly=3, annually=12.
DO $$
BEGIN
    ALTER TABLE card_multiplier_groups ADD COLUMN IF NOT EXISTS cap_period_months INTEGER;
    ALTER TABLE card_category_multipliers ADD COLUMN IF NOT EXISTS cap_period_months INTEGER;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_multiplier_groups' AND column_name = 'cap_period'
    ) THEN
        UPDATE card_multiplier_groups
        SET cap_period_months = CASE cap_period
            WHEN 'monthly'   THEN 1
            WHEN 'quarterly' THEN 3
            WHEN 'annually'  THEN 12
            ELSE NULL
        END
        WHERE cap_period_months IS NULL AND cap_period IS NOT NULL;
        ALTER TABLE card_multiplier_groups DROP COLUMN cap_period;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_category_multipliers' AND column_name = 'cap_period'
    ) THEN
        UPDATE card_category_multipliers
        SET cap_period_months = CASE cap_period
            WHEN 'monthly'   THEN 1
            WHEN 'quarterly' THEN 3
            WHEN 'annually'  THEN 12
            ELSE NULL
        END
        WHERE cap_period_months IS NULL AND cap_period IS NOT NULL;
        ALTER TABLE card_category_multipliers DROP COLUMN cap_period;
    END IF;
END $$;
