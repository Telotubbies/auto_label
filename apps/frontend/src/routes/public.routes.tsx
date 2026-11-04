import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { AcceptInvite, Forgot, Login, Reset, Signup, VerifyEmail } from '@/features/auth/Auth'
import { LoginRedirect } from './guards'

const Landing = lazy(() => import('@/features/landing/Landing'))
const LandingPreview = lazy(() => import('@/features/landing/Landing').then((m) => ({ default: m.LandingPreview })))

/** Signed-out surfaces: marketing, the auth flow, and any unknown deep link back to login. */
export const publicRoutes = (
  <>
    <Route path="/" element={<Landing />} />
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
    <Route path="/forgot" element={<Forgot />} />
    <Route path="/reset/:token" element={<Reset />} />
    <Route path="/verify/:token" element={<VerifyEmail />} />
    <Route path="/invite/:token" element={<AcceptInvite />} />
    {import.meta.env.DEV && <Route path="/__preview/:section" element={<LandingPreview />} />}
    <Route path="*" element={<LoginRedirect />} />
  </>
)
