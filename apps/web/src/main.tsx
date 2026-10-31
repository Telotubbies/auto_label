import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { Toaster } from '@/components/ui'
import './index.css'
import { initTheme } from '@/lib/theme'

initTheme()

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter><App /><Toaster /></BrowserRouter>
  </QueryClientProvider>,
)
