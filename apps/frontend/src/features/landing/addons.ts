/**
 * SAM 3.1 and the VLM ship as operator add-ons, not as part of the reference deployment.
 * The landing sections read the public capability endpoint and use this one copy so a
 * visitor never reads a promise the running stack cannot keep (I14).
 */
export interface LandingAddonState {
  available: boolean
  label: string
  detail: string
}

export function landingAddonState(addonsAvailable: boolean): LandingAddonState {
  if (addonsAvailable) {
    return {
      available: true,
      label: 'SAM 3.1 and VLM connected',
      detail: 'SAM 3.1 drafts the first pass and the VLM checks it on the connected worker.',
    }
  }
  return {
    available: false,
    label: 'Requires operator setup',
    detail: 'SAM 3.1 and the VLM are operator add-ons that are not part of this deployment. '
      + 'Labeling stays manual until an operator connects them to the worker.',
  }
}
