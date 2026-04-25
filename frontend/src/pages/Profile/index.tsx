import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { useMyWallet } from './hooks/useMyWallet'
import { WalletTab } from './components/WalletTab'
import { SpendingTab } from './components/SpendingTab'
import { SettingsTab } from './components/SettingsTab'
import { TABS, type Tab } from './lib/constants'

export default function Profile() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const activeTab: Tab =
    tabParam === 'spending' || tabParam === 'settings' ? tabParam : 'wallet'
  const setActiveTab = (tab: Tab) => {
    if (tab === 'wallet') setSearchParams({}, { replace: true })
    else setSearchParams({ tab }, { replace: true })
  }

  const { data: wallet, isLoading: walletLoading } = useMyWallet()

  if (authLoading) {
    return <div className="text-center text-slate-400 py-20">Loading...</div>
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex h-full min-h-0 max-w-5xl mx-auto w-full gap-6">
      {/* Sidebar */}
      <nav className="w-48 shrink-0 py-2">
        <ul className="space-y-1">
          {TABS.map((tab) => (
            <li key={tab.id}>
              <button
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Content */}
      <div className="flex-1 min-w-0 min-h-0 bg-slate-900 border border-slate-700 rounded-xl p-6 overflow-auto">
        {activeTab === 'wallet' && (
          <WalletTab
            cardInstances={wallet?.card_instances ?? []}
            isLoading={walletLoading}
          />
        )}
        {activeTab === 'spending' && <SpendingTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </div>
  )
}
