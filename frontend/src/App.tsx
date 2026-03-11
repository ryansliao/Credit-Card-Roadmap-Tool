import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Library from './pages/Library'
import WalletTool from './pages/WalletTool'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

function Nav() {
  const { pathname } = useLocation()
  const link = (to: string, label: string) => (
    <Link
      to={to}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        pathname === to
          ? 'bg-indigo-600 text-white'
          : 'text-slate-300 hover:text-white hover:bg-slate-700'
      }`}
    >
      {label}
    </Link>
  )
  return (
    <nav className="bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center gap-2">
      <span className="text-white font-bold text-lg mr-6">Credit Card Optimizer</span>
      {link('/', 'Wallet Tool')}
      {link('/library', 'Library')}
    </nav>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-950 text-slate-100">
          <Nav />
          <main className="p-6">
            <Routes>
              <Route path="/" element={<WalletTool />} />
              <Route path="/library" element={<Library />} />
              <Route path="/cards" element={<Navigate to="/library" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
