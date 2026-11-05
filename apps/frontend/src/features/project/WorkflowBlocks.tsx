import { ArrowDown, ArrowUp, Cpu, GitBranch, Plus, ScanText, Scissors, SlidersHorizontal, Trash2, Upload } from 'lucide-react'
import type { RegistryItem, WorkflowBlock, WorkflowBlockType } from '@/lib/types'
import { Badge, Button, Field, Input, Select } from '@/components/ui'
import { MAX_BLOCKS, canAddBlock, insertBlock, moveBlock } from './workflowChain'

const META: Record<WorkflowBlockType, { label: string; hint: string; icon: typeof Cpu }> = {
  model: { label: 'Model', hint: 'Detect or classify with a trained or zoo model', icon: Cpu },
  filter: { label: 'Filter', hint: 'Keep only the classes and confidence you need', icon: SlidersHorizontal },
  crop: { label: 'Crop', hint: 'Cut one crop per detection for a closer look', icon: Scissors },
  ocr: { label: 'OCR', hint: 'Read text from the image or the crop with a vision model', icon: ScanText },
  rule: { label: 'Rule', hint: 'Count or check a zone with the stream rule engine', icon: GitBranch },
  sink: { label: 'Sink', hint: 'Return the result or write it back as annotations', icon: Upload },
}

const ORDER: WorkflowBlockType[] = ['model', 'filter', 'crop', 'ocr', 'rule', 'sink']

export function newBlock(type: WorkflowBlockType, modelRef = ''): WorkflowBlock {
  switch (type) {
    case 'model': return { type, model_ref: modelRef, conf: null, classes: [] }
    case 'filter': return { type, classes: [], min_conf: 0.4 }
    case 'crop': return { type, expand: 0.1 }
    case 'ocr': return { type, model_ref: modelRef, prompt: 'Read all text in the image and return it verbatim.' }
    case 'rule': return { type, kind: 'count', class: '', k: 1, op: '>=', for_s: 0 }
    case 'sink': return { type, kind: 'response' }
  }
}

function classesText(classes?: string[]) {
  return (classes ?? []).join(', ')
}

function parseClasses(text: string) {
  return text.split(',').map((s) => s.trim()).filter(Boolean)
}

function RefInput({ block, models, index, onChange }: {
  block: WorkflowBlock; models: RegistryItem[]; index: number; onChange: (patch: Partial<WorkflowBlock>) => void
}) {
  const listId = `workflow-models-${index}`
  return (
    <Field label="Model" hint="Use a registry ref, e.g. ultralytics:yolo26n or trained:<id>">
      <Input list={listId} value={block.model_ref ?? ''} placeholder="ultralytics:yolo26n"
        onChange={(e) => onChange({ model_ref: e.target.value })} />
      <datalist id={listId}>
        {models.map((m) => <option key={m.ref} value={m.ref}>{m.name}{m.available ? '' : ' (unavailable)'}</option>)}
      </datalist>
    </Field>
  )
}

function ZoneFields({ block, onChange }: { block: WorkflowBlock; onChange: (patch: Partial<WorkflowBlock>) => void }) {
  const p = block.points ?? [0.1, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.9]
  const [x1, y1] = [p[0], p[1]]
  const [x2, y2] = [p[4], p[5]]
  const set = (nx1: number, ny1: number, nx2: number, ny2: number) =>
    onChange({ points: [nx1, ny1, nx2, ny1, nx2, ny2, nx1, ny2] })
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {([['x1', x1, (v: number) => set(v, y1, x2, y2)], ['y1', y1, (v: number) => set(x1, v, x2, y2)],
        ['x2', x2, (v: number) => set(x1, y1, v, y2)], ['y2', y2, (v: number) => set(x1, y1, x2, v)]] as const).map(
        ([label, value, apply]) => (
          <Field key={label} label={label}>
            <Input type="number" min={0} max={1} step={0.01} value={value}
              onChange={(e) => apply(Math.min(1, Math.max(0, Number(e.target.value))))} />
          </Field>
        ))}
    </div>
  )
}

function BlockFields({ block, models, classNames, index, onChange }: {
  block: WorkflowBlock; models: RegistryItem[]; classNames: string[]; index: number
  onChange: (patch: Partial<WorkflowBlock>) => void
}) {
  switch (block.type) {
    case 'model':
      return (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <RefInput block={block} models={models} index={index} onChange={onChange} />
          <Field label="Classes" hint="Empty = the model's own classes">
            <Input value={classesText(block.classes)} placeholder="person, helmet"
              onChange={(e) => onChange({ classes: parseClasses(e.target.value) })} />
          </Field>
          <Field label="Confidence" hint="Empty = model default">
            <Input type="number" min={0} max={1} step={0.05} value={block.conf ?? ''}
              onChange={(e) => onChange({ conf: e.target.value === '' ? null : Number(e.target.value) })} />
          </Field>
        </div>
      )
    case 'filter':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Keep classes" hint="Empty = every class">
            <Input value={classesText(block.classes)} placeholder="person, helmet"
              onChange={(e) => onChange({ classes: parseClasses(e.target.value) })} />
          </Field>
          <Field label="Minimum confidence">
            <Input type="number" min={0} max={1} step={0.05} value={block.min_conf ?? 0}
              onChange={(e) => onChange({ min_conf: Number(e.target.value) })} />
          </Field>
        </div>
      )
    case 'crop':
      return (
        <Field label="Padding around each box" hint="A share of the box size, 0–0.5">
          <Input type="number" min={0} max={0.5} step={0.05} value={block.expand ?? 0.1}
            onChange={(e) => onChange({ expand: Number(e.target.value) })} />
        </Field>
      )
    case 'ocr':
      return (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <RefInput block={block} models={models} index={index} onChange={onChange} />
          <Field label="Prompt" hint="Ask the vision model for the text you need">
            <Input value={block.prompt ?? ''} onChange={(e) => onChange({ prompt: e.target.value })} />
          </Field>
        </div>
      )
    case 'rule':
      return (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Rule">
              <Select value={block.kind ?? 'count'} onChange={(e) => onChange({ kind: e.target.value as 'count' | 'zone' })}>
                <option value="count">Count in the frame</option>
                <option value="zone">Inside a zone</option>
              </Select>
            </Field>
            <Field label="Class">
              <Select value={block.class ?? ''} onChange={(e) => onChange({ class: e.target.value })}>
                <option value="" disabled>Choose a class</option>
                {classNames.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            {(block.kind ?? 'count') === 'count' ? (
              <div className="grid grid-cols-2 gap-2">
                <Field label="Operator">
                  <Select value={block.op ?? '>='} onChange={(e) => onChange({ op: e.target.value })}>
                    {['>=', '>', '<=', '<', '=='].map((op) => <option key={op} value={op}>{op}</option>)}
                  </Select>
                </Field>
                <Field label="Count">
                  <Input type="number" min={0} step={1} value={block.k ?? 1}
                    onChange={(e) => onChange({ k: Math.max(0, Math.round(Number(e.target.value))) })} />
                </Field>
              </div>
            ) : (
              <p className="self-end text-xs text-muted-foreground">
                A zone fires when a detection&apos;s bottom-centre lands inside it.
              </p>
            )}
          </div>
          {(block.kind ?? 'count') === 'zone' && <ZoneFields block={block} onChange={onChange} />}
        </div>
      )
    case 'sink':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Output">
            <Select value={block.kind ?? 'response'} onChange={(e) => onChange({ kind: e.target.value as 'response' | 'annotations' })}>
              <option value="response">Return the result</option>
              <option value="annotations">Write annotations to the image</option>
            </Select>
          </Field>
          <p className="self-end text-xs text-muted-foreground">
            {block.kind === 'annotations'
              ? 'Boxes whose class exists in this project are added with the model as their source.'
              : 'The run panel shows detections, OCR text and rule events without changing the image.'}
          </p>
        </div>
      )
  }
}

export function WorkflowBlocks({ blocks, models, classNames, onChange }: {
  blocks: WorkflowBlock[]; models: RegistryItem[]; classNames: string[]
  onChange: (blocks: WorkflowBlock[]) => void
}) {
  const patch = (index: number, p: Partial<WorkflowBlock>) =>
    onChange(blocks.map((b, i) => (i === index ? { ...b, ...p } : b)))
  return (
    <div className="space-y-3">
      <ol className="space-y-3" aria-label="Workflow blocks">
        {blocks.map((block, index) => {
          const meta = META[block.type]
          const Icon = meta.icon
          return (
            <li key={`${block.type}-${index}`} className="relative">
              {index > 0 && <span aria-hidden className="absolute -top-3 left-6 h-3 w-px bg-border" />}
              <div className="rounded-xl border bg-card">
                <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-muted text-[11px] font-semibold tabular-nums">{index + 1}</span>
                  <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
                  <span className="text-sm font-medium">{meta.label}</span>
                  <Badge className="hidden sm:inline-flex">{meta.hint}</Badge>
                  <div className="ml-auto flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Move ${meta.label} up`}
                      disabled={moveBlock(blocks, index, -1) === blocks}
                      onClick={() => onChange(moveBlock(blocks, index, -1))}><ArrowUp className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Move ${meta.label} down`}
                      disabled={moveBlock(blocks, index, 1) === blocks}
                      onClick={() => onChange(moveBlock(blocks, index, 1))}><ArrowDown className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" aria-label={`Remove ${meta.label}`}
                      onClick={() => onChange(blocks.filter((_, i) => i !== index))}><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
                <div className="p-3">
                  <BlockFields block={block} models={models} classNames={classNames} index={index}
                    onChange={(p) => patch(index, p)} />
                </div>
              </div>
            </li>
          )
        })}
      </ol>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed p-2">
        <span className="px-1 text-xs font-medium text-muted-foreground">Add block</span>
        {ORDER.map((type) => {
          const meta = META[type]
          const Icon = meta.icon
          return (
            <Button key={type} variant="outline" size="sm" disabled={!canAddBlock(blocks, type)}
              title={type === 'sink' ? 'A workflow has exactly one sink' : `Add a ${meta.label.toLowerCase()} block`}
              onClick={() => onChange(insertBlock(blocks, newBlock(type, models[0]?.ref ?? 'ultralytics:yolo26n')))}>
              <Icon className="h-3.5 w-3.5" /> {meta.label}
            </Button>
          )
        })}
        <span className="ml-auto flex items-center gap-1 px-1 text-xs text-muted-foreground">
          <Plus className="h-3.5 w-3.5" /> {blocks.length}/{MAX_BLOCKS} blocks · one sink, last
        </span>
      </div>
    </div>
  )
}
