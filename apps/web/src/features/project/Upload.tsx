import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileArchive, FolderUp, ImagePlus, TriangleAlert, UploadCloud, X } from 'lucide-react'
import { api, post, upload } from '@/lib/api'
import { Badge, Button, Card, Field, Input, PageHeader, Progress, Select, Switch, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

const IMG = /\.(jpe?g|png|bmp|webp|tiff?)$/i
const ANN = /\.(json|txt|xml|ya?ml|labels)$/i
const stem = (n: string) => n.split('/').pop()!.replace(/\.[^.]+$/, '')

async function sha256(f: File) {
  const buf = await crypto.subtle.digest('SHA-256', await f.arrayBuffer())
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

type Picked = { file: File; path: string; dup?: boolean }
type FailedFile = { name: string; reason: string }
type IngestResult = { uploaded: number; duplicates: number; annotated: number; failed?: FailedFile[] }
type UploadSummary = { uploaded: number; duplicates: number; annotated: number; failed: FailedFile[] }

/** Collapse per-file failures into reason rows, biggest group first. */
function groupReasons(failed: FailedFile[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const f of failed) {
    const reason = f.reason?.trim() || 'Unknown error'
    counts.set(reason, (counts.get(reason) ?? 0) + 1)
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

/** Group images with their same-stem label files; shared files (data.yaml, COCO json, classes.txt) ride along in every chunk. */
function chunks(files: Picked[], size = 25): Picked[][] {
  const imgs = files.filter((f) => IMG.test(f.path) && !f.dup)
  const zips = files.filter((f) => /\.zip$/i.test(f.path))
  const anns = files.filter((f) => ANN.test(f.path))
  const stems = new Set(imgs.map((f) => stem(f.path)))
  const shared = anns.filter((a) => !stems.has(stem(a.path)))
  const out: Picked[][] = zips.map((z) => [z])
  for (let i = 0; i < imgs.length; i += size) {
    const part = imgs.slice(i, i + size)
    const ss = new Set(part.map((f) => stem(f.path)))
    out.push([...part, ...anns.filter((a) => ss.has(stem(a.path))), ...shared])
  }
  return out
}

export default function Upload() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [files, setFiles] = useState<Picked[]>([])
  const [batch, setBatch] = useState('')
  const [split, setSplit] = useState('auto')
  const [tags, setTags] = useState('')
  const [toDataset, setToDataset] = useState(true)
  const [busy, setBusy] = useState(false)
  const [prog, setProg] = useState(0)
  const [done, setDone] = useState<UploadSummary | null>(null)
  const [drag, setDrag] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const dirRef = useRef<HTMLInputElement>(null)

  const add = async (list: File[]) => {
    const picked = list.filter((f) => IMG.test(f.name) || ANN.test(f.name) || /\.zip$/i.test(f.name))
      .map((f): Picked => ({ file: f, path: (f as any).webkitRelativePath || f.name }))
    const imgs = picked.filter((p) => IMG.test(p.path))
    const hashes = await Promise.all(imgs.map((p) => sha256(p.file)))
    try {
      const { duplicates } = await post<{ duplicates: string[] }>(`${api.P(ws, project.slug)}/uploads/check`, { hashes })
      const dup = new Set(duplicates)
      imgs.forEach((p, i) => { p.dup = dup.has(hashes[i]) })
    } catch { /* server re-checks anyway */ }
    setFiles((f) => [...f, ...picked]); setDone(null)
  }

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false)
    const out: File[] = []
    const walk = async (entry: any, prefix = ''): Promise<void> => {
      if (entry.isFile) {
        const f: File = await new Promise((r) => entry.file(r))
        Object.defineProperty(f, 'webkitRelativePath', { value: prefix + f.name })
        out.push(f)
      } else if (entry.isDirectory) {
        const reader = entry.createReader()
        let batchE: any[] = []
        do { batchE = await new Promise((r) => reader.readEntries(r)); for (const c of batchE) await walk(c, `${prefix}${entry.name}/`) } while (batchE.length)
      }
    }
    const items = [...e.dataTransfer.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean)
    if (items.length) { for (const it of items) await walk(it) } else out.push(...e.dataTransfer.files)
    add(out)
  }

  const start = async () => {
    setBusy(true); setProg(0)
    const parts = chunks(files)
    const total: UploadSummary = { uploaded: 0, duplicates: 0, annotated: 0, failed: [] }
    // Images the client pre-check already knows are duplicates never reach the server, so count them here.
    total.duplicates = files.filter((f) => f.dup && IMG.test(f.path)).length
    const name = batch || `Uploaded on ${new Date().toLocaleString()}`
    try {
      for (let i = 0; i < parts.length; i++) {
        try {
          const fd = new FormData()
          parts[i].forEach((p) => fd.append('files', p.file, p.path))
          fd.append('batch_name', name); fd.append('split', split); fd.append('tags', tags); fd.append('to_dataset', String(toDataset))
          const r = await upload<IngestResult>(`${api.P(ws, project.slug)}/upload`, fd,
            (f) => setProg(((i + f) / parts.length) * 100))
          total.uploaded += r.uploaded ?? 0
          total.duplicates += r.duplicates ?? 0
          total.annotated += r.annotated ?? 0
          if (r.failed?.length) total.failed.push(...r.failed)
        } catch (e) {
          // One bad chunk must not abort the rest: record it and keep going.
          const n = parts[i].length
          total.failed.push({ name: `${n} ${n === 1 ? 'file' : 'files'}`, reason: e instanceof Error && e.message ? e.message : 'Upload failed' })
        }
        setProg(((i + 1) / parts.length) * 100)
      }
      setDone(total); setFiles([])
      qc.invalidateQueries({ queryKey: ['project', ws, project.slug] })
      const skipped = total.duplicates > 0 ? ` · ${total.duplicates} skipped` : ''
      if (total.failed.length > 0) toast.err(`Uploaded ${total.uploaded} images${skipped} · ${total.failed.length} failed — see the summary`)
      else toast.ok(`Uploaded ${total.uploaded} images${skipped}`)
    } finally { setBusy(false); setProg(100) }
  }

  const imgs = files.filter((f) => IMG.test(f.path))
  const dups = imgs.filter((f) => f.dup).length
  const annFiles = files.filter((f) => ANN.test(f.path)).length
  const zips = files.filter((f) => /\.zip$/i.test(f.path)).length
  const reasonRows = done ? groupReasons(done.failed) : []
  const shownReasons = reasonRows.slice(0, 3)
  const moreReasons = reasonRows.length - shownReasons.length

  return (
    <div className="anim-page max-w-5xl">
      <PageHeader title="Upload Data" desc="Images, folders or .zip files. Existing labels are imported automatically (COCO JSON, YOLO txt + data.yaml, Pascal VOC XML; classification: one folder per class)." />
      <div className="space-y-4 px-8 pb-10">
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
          className={cn('flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors', drag ? 'border-primary bg-accent/40' : 'bg-muted/40')}>
          <UploadCloud className="mb-3 h-10 w-10 text-primary" />
          <p className="font-semibold">Drag and drop images, folders or zips</p>
          <p className="mb-4 text-sm text-muted-foreground">Duplicates (by SHA-256) are skipped automatically.</p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => fileRef.current?.click()}><ImagePlus className="h-4 w-4" /> Select Files</Button>
            <Button variant="outline" onClick={() => dirRef.current?.click()}><FolderUp className="h-4 w-4" /> Select Folder</Button>
          </div>
          <input ref={fileRef} type="file" multiple hidden accept="image/*,.zip,.json,.txt,.xml,.yaml,.yml" onChange={(e) => { add([...(e.target.files ?? [])]); e.target.value = '' }} />
          <input ref={dirRef} type="file" multiple hidden {...({ webkitdirectory: '' } as any)} onChange={(e) => { add([...(e.target.files ?? [])]); e.target.value = '' }} />
        </div>

        {files.length > 0 && (
          <Card className="p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
              <Badge>{imgs.length - dups} new images</Badge>
              {dups > 0 && <Badge className="bg-warning/15 text-warning">{dups} duplicates skipped</Badge>}
              {annFiles > 0 && <Badge className="bg-success/15 text-success">{annFiles} annotation files</Badge>}
              {zips > 0 && <Badge><FileArchive className="h-3 w-3" /> {zips} zip</Badge>}
              <button className="ml-auto cursor-pointer text-xs text-muted-foreground hover:text-foreground" onClick={() => setFiles([])}><X className="inline h-3 w-3" /> Clear</button>
            </div>
            <div className="grid gap-4 md:grid-cols-4">
              <Field label="Batch name"><Input placeholder="Uploaded on …" value={batch} onChange={(e) => setBatch(e.target.value)} /></Field>
              <Field label="Train / Valid / Test">
                <Select className="w-full" value={split} onChange={(e) => setSplit(e.target.value)}>
                  <option value="auto">Auto 70 / 20 / 10</option><option value="keep">Use folder names (train/valid/test)</option>
                  <option value="train">All Train</option><option value="valid">All Valid</option><option value="test">All Test</option>
                </Select>
              </Field>
              <Field label="Tags" hint="Comma separated"><Input placeholder="site-a, night" value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
              <Field label="Pre-labeled images" hint={toDataset ? 'Go straight to the Dataset' : 'Go to Review on the Annotate board'}>
                <div className="flex h-9 items-center gap-2 text-sm"><Switch checked={toDataset} onChange={setToDataset} /> Add to dataset</div>
              </Field>
            </div>
            <div className="mt-3 max-h-40 overflow-y-auto rounded border bg-muted/30 p-2 font-mono text-[11px] text-muted-foreground">
              {files.slice(0, 300).map((f, i) => <div key={i} className={cn(f.dup && 'line-through opacity-60')}>{f.path}</div>)}
              {files.length > 300 && <div>… and {files.length - 300} more</div>}
            </div>
            {busy && <Progress className="mt-4" value={prog} />}
            <div className="mt-4 flex justify-end">
              <Button disabled={busy || (imgs.length - dups === 0 && !zips)} onClick={start}>{busy ? `Uploading ${Math.round(prog)}%` : 'Save and Continue'}</Button>
            </div>
          </Card>
        )}

        {done && (
          <Card data-testid="upload-summary" className="flex flex-wrap items-start gap-4 p-5">
            {done.failed.length > 0
              ? <TriangleAlert className="mt-0.5 h-8 w-8 shrink-0 text-warning" aria-hidden="true" />
              : <CheckCircle2 className="mt-0.5 h-8 w-8 shrink-0 text-success" aria-hidden="true" />}
            <div className="min-w-[12rem] flex-1 text-sm" aria-live="polite">
              <div className="font-semibold">Uploaded {done.uploaded} · duplicates skipped {done.duplicates} · failed {done.failed.length}</div>
              <div className="text-muted-foreground">{done.annotated} with imported annotations</div>
              {shownReasons.length > 0 && (
                <div className="mt-2">
                  <div className="font-medium text-warning">Failed uploads</div>
                  <ul className="mt-1 space-y-0.5 text-muted-foreground">
                    {shownReasons.map(([reason, n]) => (
                      <li key={reason}>{reason} ({n} {n === 1 ? 'file' : 'files'})</li>
                    ))}
                    {moreReasons > 0 && <li>+{moreReasons} more</li>}
                  </ul>
                </div>
              )}
            </div>
            <Button variant="outline" className="shrink-0" onClick={() => nav('../annotate')}>Annotate</Button>
            <Button className="shrink-0" onClick={() => nav('../browse')}>View Dataset</Button>
          </Card>
        )}
      </div>
    </div>
  )
}
