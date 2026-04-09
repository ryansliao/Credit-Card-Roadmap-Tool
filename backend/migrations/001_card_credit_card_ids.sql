-- Add a card_ids array column to card_credits and seed it with the cards
-- (from the global library) that natively offer each credit. This is reference
-- metadata so the UI can auto-suggest credits when a card is added to a wallet.
--
-- Card ID reference (global library):
--   1=Chase Sapphire Preferred, 2=Chase Sapphire Reserve,
--   3=Amex Gold, 4=Amex Platinum, 5=Amex Green, 6=Amex Blue Business Plus,
--   7=Chase Freedom Unlimited, 8=Chase Freedom Flex, 9=Chase Freedom,
--   10=Capital One Venture X, 11=Capital One Venture, 12=Capital One Savor,
--   13=Citi Strata Elite, 14=Citi Strata Premier, 15=Citi Strata,
--   16=Citi Custom Cash, 17=Citi Double Cash,
--   18=Bilt Palladium, 19=Bilt Obsidian, 20=Bilt Blue,
--   21=Delta Reserve, 22=Delta Platinum, 23=Delta Gold,
--   24=AAdvantage Platinum Select, 25=AAdvantage Globe, 26=AAdvantage Executive,
--   28=Discover IT, 29=Costco Anywhere Visa, 30=Discover it Cash Back

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'card_credits' AND column_name = 'card_ids'
    ) THEN
        ALTER TABLE card_credits
            ADD COLUMN card_ids INTEGER[] NOT NULL DEFAULT '{}';
    END IF;

    -- Populate card_ids for each known credit by name. Using credit_name keeps the
    -- migration idempotent and avoids hard-coding fragile primary key IDs.
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Travel Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'The Edit Hotel Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Sapphire Exclusive Tables Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'StubHub/Viagogo Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Apple TV+/Music Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Peloton Credit';
    UPDATE card_credits SET card_ids = '{1,2}'            WHERE credit_name = 'Chase Travel Hotels';
    UPDATE card_credits SET card_ids = '{3}'              WHERE credit_name = 'Dining Credit';
    UPDATE card_credits SET card_ids = '{3,4}'            WHERE credit_name = 'Uber Cash';
    UPDATE card_credits SET card_ids = '{3,21,22}'        WHERE credit_name = 'Resy Credit';
    UPDATE card_credits SET card_ids = '{3}'              WHERE credit_name = 'Dunkin Credit';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Fine Hotels & Resorts / Hotel Collection Credit';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Digital Entertainment Credit';
    UPDATE card_credits SET card_ids = '{2,4,5}'          WHERE credit_name = 'CLEAR+ Credit';
    UPDATE card_credits SET card_ids = '{2,4,5}'          WHERE credit_name = 'CLEAR Plus';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Equinox Credit';
    UPDATE card_credits SET card_ids = '{2,4,10,13,14}'   WHERE credit_name = 'Priority Pass';
    UPDATE card_credits SET card_ids = '{2,4,10,11,13,21,26}' WHERE credit_name = 'Global Entry / TSA Pre-Check';
    UPDATE card_credits SET card_ids = '{2,4,10,11,13,21,26}' WHERE credit_name = 'Global Entry / TSA PreCheck';
    UPDATE card_credits SET card_ids = '{13,14}'          WHERE credit_name = 'Citi Travel Hotel Credit';
    UPDATE card_credits SET card_ids = '{13}'             WHERE credit_name = 'Splurge Credit';
    UPDATE card_credits SET card_ids = '{13}'             WHERE credit_name = 'Blacklane Credit';
    UPDATE card_credits SET card_ids = '{18,19}'          WHERE credit_name = 'Bilt Travel Hotel Credit';
    UPDATE card_credits SET card_ids = '{21,22}'          WHERE credit_name = 'Annual Companion Certificate';
    UPDATE card_credits SET card_ids = '{26}'             WHERE credit_name = 'Admirals Club Access';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Sapphire Lounge Access';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'Lyft Credit';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'IHG One Platinum Elite Status';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Global Lounge Collection';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Marriot Bonvoy Gold Elite Status';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Hilton Honors Gold Status';
    UPDATE card_credits SET card_ids = '{21,22}'          WHERE credit_name = 'Delta Stays Credit';
    UPDATE card_credits SET card_ids = '{21,22,23,24,25,26}' WHERE credit_name = 'Free Checked Bag';
    UPDATE card_credits SET card_ids = '{21,22,23,24,25,26}' WHERE credit_name = 'Free Checked Bags';
    UPDATE card_credits SET card_ids = '{10}'             WHERE credit_name = 'Hertz President''s Circle Status';
    UPDATE card_credits SET card_ids = '{11}'             WHERE credit_name = 'Hertz Five Star Status';
    UPDATE card_credits SET card_ids = '{2}'              WHERE credit_name = 'DoorDash Credit';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Airline Incidental Credit';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Walmart+ Membership';
    UPDATE card_credits SET card_ids = '{10}'             WHERE credit_name = 'Capital One Travel Credit';
    UPDATE card_credits SET card_ids = '{1,2,7,8}'        WHERE credit_name = 'DashPass Membership';
    UPDATE card_credits SET card_ids = '{4}'              WHERE credit_name = 'Saks Fifth Avenue Credit';
    UPDATE card_credits SET card_ids = '{3}'              WHERE credit_name = 'Resy Dining Credit';
END $$;
