-- Dedupe near-duplicate card_credits rows and zero out credits whose dollar
-- value depends on the card (dining, hotel, airline incidental, etc). Fixed
-- subscription/membership credits keep their retail-price defaults.
--
-- Kept rows match the canonical names in _STANDARDIZED_CREDIT_SPECS so the
-- startup seeder does not recreate the deleted rows.

-- 1. Global Entry: keep id 24 (the $120 row), rename to canonical seed name,
--    delete id 94. The delete must run before the rename so the unique
--    constraint on credit_name does not collide.
DELETE FROM card_credits WHERE id = 94;

UPDATE card_credits
   SET credit_name = 'Global Entry / TSA PreCheck',
       credit_value = 120
 WHERE id = 24;

-- 2. Free Checked Bag(s): keep id 95 (canonical plural name), drop id 54.
--    Value is variable (depends on travel frequency), so reset to 0.
UPDATE card_credits
   SET credit_value = 0
 WHERE id = 95;

DELETE FROM card_credits WHERE id = 54;

-- 3. CLEAR: keep id 96 'CLEAR Plus' (canonical seed name) at the current $199
--    retail subscription price. Drop id 20 'CLEAR+ Credit'.
DELETE FROM card_credits WHERE id = 20;

-- 4. Variable-value credits — reset to 0. Default value should not be tied to
--    any single card since these vary across cards.
UPDATE card_credits SET credit_value = 0
 WHERE credit_name IN (
    'Airline Incidental Credit',
    'Hotel Credit',
    'Streaming Credit',
    'Saks Fifth Avenue Credit',
    'Resy Dining Credit'
 );

-- 5. Subscription/membership credits with a fixed retail value — populate
--    defaults where they were 0.
UPDATE card_credits SET credit_value = 300 WHERE credit_name = 'Equinox Credit' AND credit_value = 0;
