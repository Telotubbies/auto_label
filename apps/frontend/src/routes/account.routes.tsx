import { Navigate, Route } from 'react-router-dom'
import { AcceptInvite, Forgot, Reset, VerifyEmail } from '@/features/auth/Auth'

/** Account pages reached while signed in: email links and password changes, outside the app layout. */
export const accountRoutes = (
  <>
    <Route path="/login" element={<Navigate to="/" replace />} />
    <Route path="/signup" element={<Navigate to="/" replace />} />
    <Route path="/invite/:token" element={<AcceptInvite />} />
    {/* Account pages are reachable while signed in (email links, password changes) and sit outside the app layout. */}
    <Route path="/forgot" element={<Forgot />} />
    <Route path="/reset/:token" element={<Reset />} />
    <Route path="/verify/:token" element={<VerifyEmail />} />
  </>
)
