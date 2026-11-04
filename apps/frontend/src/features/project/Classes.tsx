import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Merge, Pencil, Plus, Trash2, Waypoints } from 'lucide-react'
import { api, del, patch, post } from '@/lib/api'
import type { LabelClass, Skeleton } from '@/lib/types'
import { Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'

type SkeletonDraft = {
  classId: string
  name: string
  hasSkeleton: boolean
  /** Raw textarea/input text; parsed and validated on save. */
  names: string
  bones: string
  flip: string
}

const parseNames = (raw: string) => raw.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)

/** "0-1, 1-2" → edge pairs; null when a token is not an index pair. */
function parseBones(raw: string): [number, number][] | null {
  const out: [number, number][] = []
  for (const part of raw.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)) {
    const m = /^(\d+)\s*-\s*(\d+)$/.exec(part)
    if (!m) return null
    out.push([Number(m[1]), Number(m[2])])
  }
  return out
}

export default function Classes() {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const base = api.P(ws, project.slug)
  const classes = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug) })
  const tags = useQuery({ queryKey: ['tags', ws, project.slug], queryFn: () => api.tags(ws, project.slug) })
  const [name, setName] = useState('')
  const [merge, setMerge] = useState<string[] | null>(null)
  const [target, setTarget] = useState('')
  const [draft, setDraft] = useState<SkeletonDraft | null>(null)
  const [formErr, setFormErr] = useState('')
  const refresh = () => { qc.invalidateQueries({ queryKey: ['classes', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['tags', ws, project.slug] }) }
  const act = (p: Promise<unknown>, ok?: string) => p.then(() => { refresh(); ok && toast.ok(ok) }).catch(toast.err)

  const openSkeleton = (c: LabelClass) => {
    const sk = c.skeleton
    setDraft({
      classId: c.id, name: c.name, hasSkeleton: !!sk,
      names: sk?.names.join(', ') ?? '',
      bones: sk?.edges.map(([a, b]) => `${a}-${b}`).join(', ') ?? '',
      flip: sk?.flip_idx?.length ? sk.flip_idx.join(', ') : '',
    })
    setFormErr('')
  }

  const saveSkeleton = () => {
    if (!draft) return
    const names = parseNames(draft.names)
    if (names.length > 100) { setFormErr('A skeleton can have at most 100 joints.'); return }
    if (!names.length) { setFormErr('Add at least one joint name.'); return }
    if (new Set(names).size !== names.length) { setFormErr('Joint names must be unique.'); return }
    const edges = parseBones(draft.bones)
    if (!edges) { setFormErr('Bones look like "0-1, 1-2" — joint indices only.'); return }
    for (const [a, b] of edges) {
      if (a >= names.length || b >= names.length) { setFormErr(`Bone ${a}-${b} points outside the joint list.`); return }
      if (a === b) { setFormErr(`Bone ${a}-${b} joins a joint to itself.`); return }
    }
    let flip_idx: number[] | undefined
    const flipParts = draft.flip.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)
    if (flipParts.length) {
      if (flipParts.some((p) => !/^\d+$/.test(p))) { setFormErr('Flip order must be comma-separated joint indices.'); return }
      flip_idx = flipParts.map(Number)
      if (flip_idx.length !== names.length || flip_idx.some((i) => i >= names.length) || new Set(flip_idx).size !== flip_idx.length) {
        setFormErr('Flip order must list every joint index exactly once.'); return
      }
    }
    const skeleton: Skeleton = { names, edges, ...(flip_idx ? { flip_idx } : {}) }
    patch(`${base}/classes/${draft.classId}`, { name: draft.name, skeleton })
      .then(() => { refresh(); setDraft(null); toast.ok('Skeleton saved') })
      .catch((e) => { setFormErr((e as Error).message); toast.err(e as Error) })
  }

  const removeSkeleton = () => {
    if (!draft) return
    patch(`${base}/classes/${draft.classId}`, { name: draft.name, skeleton: null })
      .then(() => { refresh(); setDraft(null); toast.ok('Skeleton removed') })
      .catch((e) => { setFormErr((e as Error).message); toast.err(e as Error) })
  }

  return (
    <div className="anim-page max-w-4xl">
      <PageHeader title="Classes & Tags" desc="Rename, recolor, merge or remove classes across every image." />
      <div className="space-y-6 px-8 pb-10">
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="flex-1 font-semibold">Classes</h3>
            <Input className="w-56" placeholder="New class name" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && name.trim() && act(post(`${base}/classes`, { name }).then(() => setName('')))} />
            <Button size="sm" disabled={!name.trim()} onClick={() => act(post(`${base}/classes`, { name }).then(() => setName('')))}><Plus className="h-4 w-4" /> Add</Button>
            {(classes.data?.length ?? 0) > 1 && <Button size="sm" variant="outline" onClick={() => { setMerge([]); setTarget('') }}><Merge className="h-4 w-4" /> Merge</Button>}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="py-2">Color</th><th>Name</th><th className="text-right">Annotations</th><th>Skeleton</th><th /></tr></thead>
              <tbody>
                {classes.data?.map((c) => (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="py-2"><input type="color" value={c.color} onChange={(e) => act(patch(`${base}/classes/${c.id}`, { name: c.name, color: e.target.value }))} className="h-7 w-9 cursor-pointer rounded border" aria-label={`Color for ${c.name}`} /></td>
                    <td className="font-medium">{c.name}</td>
                    <td className="text-right tabular-nums">{c.count}</td>
                    <td className="py-2">
                      <Button variant="outline" size="sm" data-testid="edit-skeleton" onClick={() => openSkeleton(c)}
                        aria-label={c.skeleton ? `Edit skeleton for ${c.name} (${c.skeleton.names.length} keypoints)` : `Add skeleton for ${c.name}`}>
                        <Waypoints className="h-3.5 w-3.5" aria-hidden="true" />
                        {c.skeleton ? `${c.skeleton.names.length} keypoints` : 'Edit skeleton'}
                      </Button>
                    </td>
                    <td className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => { const n = prompt('Rename class', c.name); n && act(patch(`${base}/classes/${c.id}`, { name: n }), 'Renamed') }} aria-label="Rename"><Pencil className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => confirm(`Delete "${c.name}" and its ${c.count} annotations?`) && act(del(`${base}/classes/${c.id}`), 'Deleted')} aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {classes.isSuccess && !classes.data.length && <EmptyState title="No classes yet." hint="Add classes here or while annotating." />}
        </Card>
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {tags.data?.map((t) => (
              <span key={t.name} className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
                {t.name} <span className="text-xs text-muted-foreground">{t.count}</span>
                <button className="cursor-pointer text-muted-foreground hover:text-foreground" onClick={() => { const n = prompt('Rename tag', t.name); n && act(post(`${base}/tags/rename`, { name: t.name, new_name: n })) }} aria-label="Rename tag"><Pencil className="h-3 w-3" /></button>
                <button className="cursor-pointer text-muted-foreground hover:text-destructive" onClick={() => confirm(`Remove tag "${t.name}" from ${t.count} images?`) && act(post(`${base}/tags/rename`, { name: t.name, new_name: null }))} aria-label="Delete tag"><Trash2 className="h-3 w-3" /></button>
              </span>
            ))}
            {tags.isSuccess && !tags.data.length && <p className="text-sm text-muted-foreground">No tags yet — add them on upload, in bulk on the Dataset page, or in the editor.</p>}
          </div>
        </Card>
      </div>
      <Modal open={merge !== null} onClose={() => setMerge(null)} title="Merge classes">
        <p className="mb-3 text-sm text-muted-foreground">Selected classes are relabeled to the target and then removed.</p>
        <div className="mb-3 space-y-1">
          {classes.data?.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-primary" checked={merge?.includes(c.id) ?? false}
              onChange={(e) => setMerge((m) => (e.target.checked ? [...(m ?? []), c.id] : (m ?? []).filter((x) => x !== c.id)))} />
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} /> {c.name} ({c.count})</label>
          ))}
        </div>
        <Select className="w-full" value={target} onChange={(e) => setTarget(e.target.value)}><option value="">Merge into…</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setMerge(null)}>Cancel</Button>
          <Button disabled={!target || !merge?.length} onClick={() => { act(post(`${base}/classes/merge`, { source_ids: merge, target_id: target }), 'Merged'); setMerge(null) }}>Merge</Button></div>
      </Modal>
      <Modal open={draft !== null} onClose={() => setDraft(null)} title={draft ? `Skeleton · ${draft.name}` : 'Skeleton'}>
        {draft && (
          <div data-testid="skeleton-modal" className="space-y-4">
            <p className="text-sm text-muted-foreground">Joints and bones are shared by every annotation of this class. Keypoint interpolation and tracking use this order.</p>
            <Field label="Joint names" hint="Comma or newline separated · up to 100 joints · order defines the index used by bones and flip order.">
              <textarea className="min-h-24 w-full rounded-md border bg-background p-2 text-sm" value={draft.names} onChange={(e) => setDraft({ ...draft, names: e.target.value })} placeholder="nose, left_eye, right_eye, left_shoulder…" spellCheck={false} />
            </Field>
            <Field label="Bones" hint='Index pairs such as "0-1, 1-2". Leave empty for a joint-only skeleton.'>
              <Input value={draft.bones} onChange={(e) => setDraft({ ...draft, bones: e.target.value })} placeholder="0-1, 1-2, 2-3" spellCheck={false} />
            </Field>
            <Field label="Flip order (optional)" hint="One joint index per joint, left-to-right swapped — used by horizontal augmentation.">
              <Input value={draft.flip} onChange={(e) => setDraft({ ...draft, flip: e.target.value })} placeholder="1, 0, 3, 2" spellCheck={false} />
            </Field>
            {formErr && <p role="alert" className="text-sm text-destructive">{formErr}</p>}
            <div className="flex flex-wrap justify-end gap-2">
              {draft.hasSkeleton && <Button variant="ghost" className="text-destructive" onClick={removeSkeleton}>Remove skeleton</Button>}
              <Button variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
              <Button onClick={saveSkeleton}>Save skeleton</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
