import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { useMyWallet } from './hooks/useMyWallet'
import { WalletTab } from './components/WalletTab'
import { SpendingTab } from './components/SpendingTab'
import { AppearanceTab } from './components/AppearanceTab'
import { SettingsTab } from './components/SettingsTab'
import { TABS, type Tab } from './lib/constants'

export default function Profile() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const activeTab: Tab =
    tabParam === 'spending' || tabParam === 'appearance' || tabParam === 'settings'
      ? tabParam
      : 'wallet'
  const setActiveTab = (tab: Tab) => {
    if (tab === 'wallet') setSearchParams({}, { replace: true })
    else setSearchParams({ tab }, { replace: true })
  }

  const { data: wallet, isLoading: walletLoading } = useMyWallet()

  if (authLoading) {
    return <div className="text-center text-ink-muted py-20">Loading...</div>
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex h-full min-h-0 max-w-5xl mx-auto w-full gap-6">
      {/* Sidebar */}
      <nav className="w-48 shrink-0 py-2">
        <ul className="space-y-0.5">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id
            return (
              <li key={tab.id}>
                <button
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative w-full flex items-center gap-3 pl-4 pr-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-ink bg-surface-2'
                      : 'text-ink-faint hover:text-ink hover:bg-surface-2/60'
                  }`}
                >
                  {isActive && (
                    <span aria-hidden="true" className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />
                  )}
                  {tab.icon}
                  {tab.label}
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Content */}
      <div className="flex-1 min-w-0 min-h-0 bg-surface rounded-xl shadow-card p-6 overflow-auto">
        {activeTab === 'wallet' && (
          <WalletTab
            cardInstances={wallet?.card_instances ?? []}
            isLoading={walletLoading}
          />
        )}
        {activeTab === 'spending' && <SpendingTab />}
        {activeTab === 'appearance' && <AppearanceTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </div>
  )
}
