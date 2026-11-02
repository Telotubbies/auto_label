/** The model name shown in the running-autolabel banner. Lean job payloads omit `params`, so the
 *  banner must never dereference it directly (I2). */
export function autolabelLabel(params?: { model_ref?: string | null; method?: string } | null): string {
  return params?.model_ref ?? (params?.method === 'sam' ? 'SAM 3.1' : 'model')
}
