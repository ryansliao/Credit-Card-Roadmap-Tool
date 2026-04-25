-- Drop the wallet_currency_balances table.
-- The balance/tracking feature was never wired to the frontend (API methods
-- and query keys existed but no useQuery consumed them). The table, its
-- endpoints, service methods, model, and schemas have all been removed;
-- this migration cleans up the orphaned table.
IF EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_currency_balances')
      AND type = N'U'
)
BEGIN
    DROP TABLE wallet_currency_balances;
END
GO
