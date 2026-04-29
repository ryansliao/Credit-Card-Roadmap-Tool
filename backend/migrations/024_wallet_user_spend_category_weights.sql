-- Migration 024: add wallet_user_spend_category_weights table.
--
-- Sparse per-wallet override of UserSpendCategoryMapping.default_weight,
-- one row per (wallet, user_category, earn_category) the user has
-- customized. Absence means inherit the global default. Lets users tune
-- the fan-out from a UserSpendCategory (e.g. "Travel") into its
-- underlying earn categories (Flights/Hotels/Travel-other) without
-- affecting other users or the seeded YAML defaults.
--
-- Idempotent. Re-runnable.

------------------------------------------------------------------------------
-- 1. Create wallet_user_spend_category_weights.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_user_spend_category_weights') AND type = 'U'
)
    CREATE TABLE wallet_user_spend_category_weights (
        id                INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        wallet_id         INT NOT NULL,
        user_category_id  INT NOT NULL,
        earn_category_id  INT NOT NULL,
        weight            FLOAT NOT NULL,
        created_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_user_spend_category_weights_created_at
                              DEFAULT SYSUTCDATETIME(),
        updated_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_user_spend_category_weights_updated_at
                              DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_wallet_user_spend_category_weights_wallet
            FOREIGN KEY (wallet_id)
            REFERENCES wallets(id)
            ON DELETE CASCADE,
        CONSTRAINT FK_wallet_user_spend_category_weights_user_category
            FOREIGN KEY (user_category_id)
            REFERENCES user_spend_categories(id)
            ON DELETE CASCADE,
        CONSTRAINT FK_wallet_user_spend_category_weights_earn_category
            FOREIGN KEY (earn_category_id)
            REFERENCES spend_categories(id),
        CONSTRAINT UX_wallet_user_spend_category_weights
            UNIQUE (wallet_id, user_category_id, earn_category_id)
    );
GO
