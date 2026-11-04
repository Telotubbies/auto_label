/**
 * Pure capability predicate for the landing page (I14). Kept free of React/query imports so the
 * claim tests can exercise it without a built bundle.
 *
 * The add-on is only available when the operator provisioned both halves: SAM is enabled and a
 * VLM endpoint was explicitly configured. A runtime-loaded SAM alone is not a VLM.
 */
export interface PublicCapabilities {
  sam?: { enabled?: boolean; loaded?: boolean; error?: string | null }
  vlm?: { configured?: boolean }
}

export function addonsAvailable(config?: PublicCapabilities): boolean {
  return config?.sam?.enabled === true && config?.vlm?.configured === true
}
