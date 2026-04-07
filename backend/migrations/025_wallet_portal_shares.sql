-- Phase B: per-wallet per-issuer travel portal shares.
--
-- Stores the user's "I book X% of my travel through this issuer's portal"
-- setting. The calculator uses this to gate is_portal=True multipliers
-- (e.g., Chase Freedom Flex's 5x on Chase Travel) — only `share` of the
-- relevant category's spend is eligible for the portal premium; the rest
-- earns the card's non-portal rate on that category.
--
-- One row per (wallet, issuer). Default behavior when no row exists is
-- share=0, which means portal-only multipliers contribute nothing to EV
-- until the user opts in.
DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS wallet_portal_shares (
        id          SERIAL PRIMARY KEY,
        wallet_id   INTEGER NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
        issuer_id   INTEGER NOT NULL REFERENCES issuers(id) ON DELETE CASCADE,
        share       REAL NOT NULL CHECK (share >= 0 AND share <= 1),
        UNIQUE (wallet_id, issuer_id)
    );
    CREATE INDEX IF NOT EXISTS idx_wallet_portal_shares_wallet
        ON wallet_portal_shares(wallet_id);
END $$;
