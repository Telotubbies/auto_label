import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Merge, Pencil, Plus, Trash2 } from 'lucide-react'
import { api, del, patch, post } from '@/lib/api'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'

export default function Classes() {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const base = api.P(ws, project.slug)
  const classes = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug) })
  const tags = useQuery({ queryKey: ['tags', ws, project.slug], queryFn: () => api.tags(ws, project.slug) })
  const [name, setName] = useState('')
  const [merge, setMerge] = useState<string[] | null>(null)
  const [target, setTarget] = useState('')
  const refresh = () => { qc.invalidateQueries({ queryKey: ['classes', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['tags', ws, project.slug] }) }
  const act = (p: Promise<unknown>, ok?: string) => p.then(() => { refresh(); ok && toast.ok(ok) }).catch(toast.err)

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
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="py-2">Color</th><th>Name</th><th className="text-right">Annotations</th><th /></tr></thead>
            <tbody>
              {classes.data?.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="py-2"><input type="color" value={c.color} onChange={(e) => act(patch(`${base}/classes/${c.id}`, { name: c.name, color: e.target.value }))} className="h-7 w-9 cursor-pointer rounded border" aria-label={`Color for ${c.name}`} /></td>
                  <td className="font-medium">{c.name}</td>
                  <td className="text-right tabular-nums">{c.count}</td>
                  <td className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => { const n = prompt('Rename class', c.name); n && act(patch(`${base}/classes/${c.id}`, { name: n }), 'Renamed') }} aria-label="Rename"><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => confirm(`Delete "${c.name}" and its ${c.count} annotations?`) && act(del(`${base}/classes/${c.id}`), 'Deleted')} aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
    </div>
  )
}
