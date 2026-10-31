import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileArchive, FolderUp, ImagePlus, UploadCloud, X } from 'lucide-react'
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
  const [done, setDone] = useState<{ uploaded: number; duplicates: number; annotated: number } | null>(null)
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
    const total = { uploaded: 0, duplicates: files.filter((f) => f.dup).length, annotated: 0 }
    const name = batch || `Uploaded on ${new Date().toLocaleString()}`
    try {
      for (let i = 0; i < parts.length; i++) {
        const fd = new FormData()
        parts[i].forEach((p) => fd.append('files', p.file, p.path))
        fd.append('batch_name', name); fd.append('split', split); fd.append('tags', tags); fd.append('to_dataset', String(toDataset))
        const r = await upload<{ uploaded: number; duplicates: number; annotated: number }>(`${api.P(ws, project.slug)}/upload`, fd,
          (f) => setProg(((i + f) / parts.length) * 100))
        total.uploaded += r.uploaded; total.duplicates += r.duplicates; total.annotated += r.annotated
      }
      setDone(total); setFiles([])
      qc.invalidateQueries({ queryKey: ['project', ws, project.slug] })
      toast.ok(`Uploaded ${total.uploaded} images`)
    } catch (e) { toast.err(e as Error) } finally { setBusy(false); setProg(100) }
  }

  const imgs = files.filter((f) => IMG.test(f.path))
  const dups = imgs.filter((f) => f.dup).length
  const annFiles = files.filter((f) => ANN.test(f.path)).length
  const zips = files.filter((f) => /\.zip$/i.test(f.path)).length

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
              {dups > 0 && <Badge className="bg-amber-100 text-amber-800">{dups} duplicates skipped</Badge>}
              {annFiles > 0 && <Badge className="bg-green-100 text-green-800">{annFiles} annotation files</Badge>}
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
          <Card className="flex items-center gap-4 p-5">
            <CheckCircle2 className="h-8 w-8 text-green-600" />
            <div className="flex-1 text-sm">
              <div className="font-semibold">{done.uploaded} images uploaded</div>
              <div className="text-muted-foreground">{done.annotated} with imported annotations · {done.duplicates} duplicates skipped</div>
            </div>
            <Button variant="outline" onClick={() => nav('../annotate')}>Annotate</Button>
            <Button onClick={() => nav('../browse')}>View Dataset</Button>
          </Card>
        )}
      </div>
    </div>
  )
}
