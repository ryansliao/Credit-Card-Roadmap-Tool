export const queryKeys = {
  // Wallet (singular).
  myWalletWithScenarios: () => ['wallet-with-scenarios'] as const,
  ownedCardInstances: () => ['wallet-card-instances'] as const,
  walletSpendItemsSingular: () => ['wallet-spend-items-singular'] as const,

  // Scenarios.
  scenarios: () => ['scenarios'] as const,
  scenario: (scenarioId: number | null) => ['scenario', scenarioId] as const,
  scenarioFutureCards: (scenarioId: number | null) =>
    ['scenario-future-cards', scenarioId] as const,
  scenarioOverlays: (scenarioId: number | null) =>
    ['scenario-overlays', scenarioId] as const,
  scenarioResults: (scenarioId: number | null) =>
    ['scenario-results', scenarioId] as const,
  scenarioLatestResults: (scenarioId: number | null) =>
    ['scenario-latest-results', scenarioId] as const,
  scenarioRoadmap: (scenarioId: number | null) =>
    ['scenario-roadmap', scenarioId] as const,
  scenarioCurrencies: (scenarioId: number | null) =>
    ['scenario-currencies', scenarioId] as const,
  scenarioCategoryPriorities: (scenarioId: number | null) =>
    ['scenario-category-priorities', scenarioId] as const,
  scenarioPortalShares: (scenarioId: number | null) =>
    ['scenario-portal-shares', scenarioId] as const,
  scenarioCardCredits: (scenarioId: number | null, instanceId: number | null) =>
    ['scenario-card-credits', scenarioId, instanceId] as const,

  // Reference data.
  cards: () => ['cards'] as const,
  credits: () => ['credits'] as const,
  currencies: () => ['currencies'] as const,
  travelPortals: ['travel-portals'] as const,
  issuerApplicationRules: () => ['issuer-application-rules'] as const,
} as const
