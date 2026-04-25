-- Add include_subs toggle to wallets. When False (0), the calculator excludes
-- Sign Up Bonus contributions (sub_points, sub_spend_earn, sub_cash,
-- sub_secondary_points) and disables SUB-window allocation priority when
-- computing EAF / recurring income / per-card earn. Manually tracked
-- WalletCurrencyBalance rows are not affected.
--
-- Defaults to 1 (enabled) so existing wallets keep their pre-migration
-- calculation behaviour.
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'wallets')
      AND name = 'include_subs'
)
BEGIN
    ALTER TABLE wallets
    ADD include_subs BIT NOT NULL
        CONSTRAINT DF_wallets_include_subs DEFAULT 1;
END
GO
