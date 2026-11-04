import { Suspense } from 'react'
import { Routes } from 'react-router-dom'
import { useApp } from '@/lib/store'
import { Loading } from '@/routes/guards'
import { appRoutes, publicRoutes } from '@/routes'

export default function App() {
  const authed = useApp((s) => s.authed)
  return (
    <Suspense fallback={<Loading />}>
      <Routes>{authed ? appRoutes : publicRoutes}</Routes>
    </Suspense>
  )
}
