/** The model name shown in the running-autolabel banner. Lean job payloads omit `params`, so the
 *  banner must never dereference it directly (I2). */
export function autolabelLabel(params?: { model_ref?: string | null; method?: string } | null): string {
  return params?.model_ref ?? (params?.method === 'sam' ? 'SAM 3.1' : 'model')
}

/** The `autolabel` value a hub link carries; blank means the link asked for nothing. */
export function autolabelParam(sp: URLSearchParams): string | null {
  return sp.get('autolabel')?.trim() || null
}

/** The link's model when the registry still lists it; `null` means keep the default.
 *  An unavailable model is returned too: the dialog's reason line explains why Run is disabled. */
export function pickInitialRef<T extends { ref: string }>(initial: string | null | undefined, items: readonly T[]): string | null {
  return initial && items.some((m) => m.ref === initial) ? initial : null
}
