import { Component, type ErrorInfo, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import WalletTool from './pages/WalletTool/index'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h2>
          <p className="text-slate-400 text-sm mb-4">{this.state.error?.message}</p>
          <button
            className="px-4 py-2 bg-slate-700 rounded text-sm hover:bg-slate-600"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

function Nav() {
  return (
    <nav className="bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center gap-2">
      <span className="text-white font-bold text-lg mr-6">Credit Card Optimizer</span>
    </nav>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="h-dvh min-h-0 flex flex-col overflow-hidden bg-slate-950 text-slate-100">
          <Nav />
          <main className="flex-1 min-h-0 p-6 flex flex-col overflow-hidden">
            <ErrorBoundary>
              <div className="flex-1 min-h-0 min-w-0 flex flex-col">
                <Routes>
                  <Route path="/" element={<WalletTool />} />
                </Routes>
              </div>
            </ErrorBoundary>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
