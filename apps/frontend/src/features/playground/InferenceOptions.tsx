import { Field, Input, Select, Switch } from '@/components/ui'
import { MATCH_METRICS, POSTPROCESS, type InferOptions, type ModelOptions, type SliceOptions } from './inferOptions'

const POST_HINT: Record<SliceOptions['post'], string> = {
  NMS: 'Keep the strongest box and drop the ones that overlap it.',
  NMM: 'Merge overlapping boxes into one box that spans them all.',
  GREEDYNMM: 'Merge, and keep merging into the box as it grows. Best for objects cut by a slice edge.',
  LSNMS: 'Same boxes as NMS, built for very many detections.',
}

const num = (v: string) => (v === '' ? null : Number(v))

function Toggle({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <span className="mt-0.5 shrink-0"><Switch checked={checked} onChange={onChange} label={label} /></span>
      <span>{label}{hint && <span className="block text-xs text-muted-foreground">{hint}</span>}</span>
    </label>
  )
}

function Slider({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <Field label={`${label} ${value}%`}>
      <input type="range" min={min} max={max} value={value} aria-label={label} className="w-full accent-primary"
        onChange={(e) => onChange(+e.target.value)} />
    </Field>
  )
}

/** Every slice-inference (SAHI) and inference-time option the server accepts. Slicing sits behind task_30. */
export function InferenceOptions({ value, onChange, slicingOn }: { value: InferOptions; onChange: (v: InferOptions) => void; slicingOn: boolean }) {
  const s = value.slice
  const m = value.model
  const setS = (p: Partial<SliceOptions>) => onChange({ ...value, slice: { ...s, ...p } })
  const setM = (p: Partial<ModelOptions>) => onChange({ ...value, model: { ...m, ...p } })

  return (
    <div className="space-y-3">
      {slicingOn && (
        <fieldset className="space-y-3 rounded-lg border p-3">
          <legend className="px-1 text-sm font-medium">Sliced inference (SAHI)</legend>
          <Toggle label="Slice the image" hint="Runs the model on overlapping crops and merges the boxes. For large images with small objects."
            checked={s.on} onChange={(on) => setS({ on })} />
          {s.on && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2"><Toggle label="Auto slice size" hint="Picks the slice size and overlap from the image resolution." checked={s.auto} onChange={(auto) => setS({ auto })} /></div>
              {!s.auto && (
                <>
                  <Field label="Slice width (px)"><Input type="number" min={64} max={4096} value={s.width} onChange={(e) => setS({ width: +e.target.value })} /></Field>
                  <Field label="Slice height (px)"><Input type="number" min={64} max={4096} value={s.height} onChange={(e) => setS({ height: +e.target.value })} /></Field>
                  <Slider label="Overlap width" value={s.overlapW} min={0} max={90} onChange={(overlapW) => setS({ overlapW })} />
                  <Slider label="Overlap height" value={s.overlapH} min={0} max={90} onChange={(overlapH) => setS({ overlapH })} />
                </>
              )}
              <div className="col-span-2"><Toggle label="Also run the whole image" hint="Adds one full-image pass so large objects stay whole." checked={s.standard} onChange={(standard) => setS({ standard })} /></div>
              <Slider label="Keep clipped boxes above" value={s.minArea} min={0} max={100} onChange={(minArea) => setS({ minArea })} />
              <Field label="Post-processing" hint={POST_HINT[s.post]}>
                <Select value={s.post} onChange={(e) => setS({ post: e.target.value as SliceOptions['post'] })} className="w-full">
                  {POSTPROCESS.map((p) => <option key={p} value={p}>{p}</option>)}
                </Select>
              </Field>
              <Field label="Match metric" hint="IOS also catches a small box inside a big one.">
                <Select value={s.metric} onChange={(e) => setS({ metric: e.target.value as SliceOptions['metric'] })} className="w-full">
                  {MATCH_METRICS.map((p) => <option key={p} value={p}>{p}</option>)}
                </Select>
              </Field>
              <Slider label="Match threshold" value={s.threshold} min={0} max={100} onChange={(threshold) => setS({ threshold })} />
              <div className="col-span-2"><Toggle label="Class-agnostic merge" hint="Merge boxes even when their classes differ." checked={s.agnostic} onChange={(agnostic) => setS({ agnostic })} /></div>
            </div>
          )}
        </fieldset>
      )}

      <fieldset className="space-y-3 rounded-lg border p-3">
        <legend className="px-1 text-sm font-medium">Inference techniques</legend>
        <p className="text-xs text-muted-foreground">For YOLO models. Other models in a comparison ignore these and say so.</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Image size (px)" hint="Empty = the model's own size.">
            <Input type="number" min={32} max={4096} step={32} placeholder="640" value={m.imgsz ?? ''} onChange={(e) => setM({ imgsz: num(e.target.value) })} />
          </Field>
          <Field label="Max detections" hint="Empty = 300.">
            <Input type="number" min={1} max={3000} placeholder="300" value={m.maxDet ?? ''} onChange={(e) => setM({ maxDet: num(e.target.value) })} />
          </Field>
          <div className="col-span-2">
            <Field label="Only these class ids" hint="Comma-separated, e.g. 0, 2. Empty = every class.">
              <Input placeholder="0, 2" value={m.classIds} onChange={(e) => setM({ classIds: e.target.value })} />
            </Field>
          </div>
        </div>
        <div className="space-y-2">
          <Toggle label="Test-time augmentation (TTA)" hint="Runs flipped and scaled copies and merges them. Slower, often more accurate." checked={m.augment} onChange={(augment) => setM({ augment })} />
          <Toggle label="Agnostic NMS" hint="Suppress overlapping boxes across classes." checked={m.agnosticNms} onChange={(agnosticNms) => setM({ agnosticNms })} />
          <Toggle label="Half precision (FP16)" hint="Faster on a GPU, slightly less exact." checked={m.half} onChange={(half) => setM({ half })} />
          <Toggle label="Retina masks" hint="Segmentation masks at full image resolution." checked={m.retina} onChange={(retina) => setM({ retina })} />
        </div>
      </fieldset>
    </div>
  )
}
