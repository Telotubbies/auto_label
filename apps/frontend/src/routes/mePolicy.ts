/**
 * Only a 401 (the session is actually dead) may sign the user out. A network error, a 5xx or a
 * timeout leaves the token valid, so the gate shows a retryable error instead of the login page.
 */
export const meNeedsLogin = (error: unknown) => (error as { status?: number } | null)?.status === 401
