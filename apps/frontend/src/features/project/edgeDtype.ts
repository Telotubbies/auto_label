/** Edge export dtype helpers. A preset lists the dtypes it can build, default first; a build of a non-default
 *  dtype is stored as `preset:dtype`, so FP32 and FP16 of one model sit side by side. */
export interface DtypeOption { id: string; label: string; default: boolean; needs_data: boolean }
export interface PresetLike { id: string; label: string; dtypes?: DtypeOption[] }

/** The dtype to use: the picked one when this preset offers it, otherwise the preset's default. */
export function pickDtype(preset: PresetLike | undefined, picked: string): string {
  const opts = preset?.dtypes ?? []
  if (opts.some((d) => d.id === picked)) return picked
  return opts.find((d) => d.default)?.id ?? ''
}

/** The export request: the dtype is sent only when it differs from the preset's default. */
export function buildBody(preset: PresetLike, dtype: string): { preset: string; dtype?: string } {
  const isDefault = preset.dtypes?.find((d) => d.default)?.id === dtype
  return !dtype || isDefault ? { preset: preset.id } : { preset: preset.id, dtype }
}

/** "NCNN · FP16" for `ncnn:fp16`; a preset with one dtype is just its label. */
export function artifactLabel(list: PresetLike[], key: string): string {
  const [id, dtype] = key.split(':')
  const preset = list.find((p) => p.id === id)
  const name = preset?.label ?? id
  const shown = dtype ?? preset?.dtypes?.find((d) => d.default)?.id
  return shown && (dtype || (preset?.dtypes?.length ?? 0) > 1) ? `${name} · ${shown.toUpperCase()}` : name
}
