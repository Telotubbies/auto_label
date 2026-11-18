/** Inference options of the Playground: slice inference (SAHI) and inference-time techniques.
 *  Pure, so a node test can run it: `optionFields` turns the state into form fields and sends only what is on. */
export const POSTPROCESS = ['NMS', 'NMM', 'GREEDYNMM', 'LSNMS'] as const
export const MATCH_METRICS = ['IOU', 'IOS'] as const

export interface SliceOptions {
  on: boolean
  auto: boolean
  width: number
  height: number
  overlapW: number       // percent
  overlapH: number       // percent
  standard: boolean      // also run the whole image
  minArea: number        // percent of a clipped box that must stay visible
  post: (typeof POSTPROCESS)[number]
  metric: (typeof MATCH_METRICS)[number]
  threshold: number      // percent
  agnostic: boolean
}

export interface ModelOptions {
  imgsz: number | null
  maxDet: number | null
  agnosticNms: boolean
  augment: boolean       // test-time augmentation
  half: boolean
  retina: boolean
  classIds: string
}

export interface InferOptions { slice: SliceOptions; model: ModelOptions }

export const DEFAULT_OPTIONS: InferOptions = {
  slice: { on: false, auto: false, width: 640, height: 640, overlapW: 20, overlapH: 20, standard: false, minArea: 10,
    post: 'GREEDYNMM', metric: 'IOS', threshold: 50, agnostic: false },
  model: { imgsz: null, maxDet: null, agnosticNms: false, augment: false, half: false, retina: false, classIds: '' },
}

const ratio = (percent: number) => String(percent / 100)

export function optionFields({ slice, model }: InferOptions): [string, string][] {
  const out: [string, string][] = []
  if (slice.on) {
    if (slice.auto) out.push(['auto_slice', 'true'])
    else out.push(['slice_width', String(slice.width)], ['slice_height', String(slice.height)],
      ['overlap_width_ratio', ratio(slice.overlapW)], ['overlap_height_ratio', ratio(slice.overlapH)])
    if (slice.standard) out.push(['perform_standard_pred', 'true'])
    out.push(['min_area_ratio', ratio(slice.minArea)], ['postprocess_type', slice.post],
      ['postprocess_match_metric', slice.metric], ['postprocess_match_threshold', ratio(slice.threshold)])
    if (slice.agnostic) out.push(['postprocess_class_agnostic', 'true'])
  }
  if (model.imgsz) out.push(['imgsz', String(model.imgsz)])
  if (model.maxDet) out.push(['max_det', String(model.maxDet)])
  if (model.agnosticNms) out.push(['agnostic_nms', 'true'])
  if (model.augment) out.push(['augment', 'true'])
  if (model.half) out.push(['half', 'true'])
  if (model.retina) out.push(['retina_masks', 'true'])
  const ids = model.classIds.split(',').map((x) => x.trim()).filter(Boolean).join(',')
  if (ids) out.push(['class_ids', ids])
  return out
}
