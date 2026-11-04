import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, ShieldCheck, Trash2 } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import { Button, Card, EmptyState, Input, Select, Spinner, toast } from '@/components/ui'
import { ErrorNote, Loading, pct } from './shared'

export default function Honeypots({ ws, slug }: { ws: string; slug: string }) {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [imageId, setImageId] = useState('')
  const q = useQuery({ queryKey: ['labeling-honeypots', ws, slug], queryFn: () => api.honeypots(ws, slug) })
  const picker = useQuery({
    queryKey: ['honeypot-images', ws, slug, search],
    queryFn: () => api.images(ws, slug, { q: search, limit: 100 }),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })
  const create = useMutation({
    mutationFn: () => api.createHoneypot(ws, slug, { image_id: imageId }),
    onSuccess: () => {
      toast.ok('Image marked as ground truth')
      setImageId('')
      qc.invalidateQueries({ queryKey: ['labeling-honeypots', ws, slug] })
      qc.invalidateQueries({ queryKey: ['labeling-dashboard', ws, slug] })
    },
    onError: (e) => toast.err(e as Error),
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteHoneypot(ws, slug, id),
    onSuccess: () => {
      toast.ok('Ground-truth image removed')
      qc.invalidateQueries({ queryKey: ['labeling-honeypots', ws, slug] })
      qc.invalidateQueries({ queryKey: ['labeling-dashboard', ws, slug] })
    },
    onError: (e) => toast.err(e as Error),
  })

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-lg font-semibold tracking-tight">Mark an image as ground truth</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Its current annotations become the answer key. Labelers never see which images are honeypots; their accuracy is scored on every attempt.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
            <Input className="pl-8" placeholder="Search filename" aria-label="Search images" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select className="min-w-0 sm:w-72" aria-label="Ground-truth image" value={imageId}
            onChange={(e) => setImageId(e.target.value)} disabled={picker.isLoading}>
            <option value="">{picker.isLoading ? 'Loading images…' : 'Choose an image…'}</option>
            {picker.data?.items.map((im) => <option key={im.id} value={im.id}>{im.name}</option>)}
          </Select>
          <Button disabled={!imageId || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? <Spinner className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />} Mark as ground truth
          </Button>
        </div>
        {picker.isError && <p role="alert" className="mt-2 text-xs text-destructive">{(picker.error as Error).message}</p>}
      </Card>

      {q.isLoading ? <Loading /> : q.isError ? <ErrorNote error={q.error} /> : !q.data?.items.length ? (
        <Card className="p-4">
          <EmptyState title="No ground-truth images yet." hint="Mark an image as ground truth to score labeler accuracy. Labelers never see which images are honeypots." />
        </Card>
      ) : (
        <>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto" role="region" aria-label="Ground-truth images table" tabIndex={0}>
              <table className="w-full min-w-[560px] text-sm">
                <caption className="px-3 pt-3 text-left text-xs text-muted-foreground">Ground-truth images and their scores.</caption>
                <thead>
                  <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                    <th scope="col" className="px-3 py-2 font-medium">Image</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">GT labels</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Attempts</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Accuracy</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium"><span className="sr-only">Remove</span></th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((h) => (
                    <tr key={h.id} className="border-b last:border-0">
                      <th scope="row" className="px-3 py-2 text-left font-medium">
                        <span className="flex items-center gap-2">
                          <img src={fileUrl(h.thumbnail)} alt="" loading="lazy" className="h-9 w-14 shrink-0 rounded border bg-muted object-cover" />
                          <span className="min-w-0 truncate">{h.name}</span>
                        </span>
                      </th>
                      <td className="px-3 py-2 text-right tabular-nums">{h.annotations}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{h.attempts}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{pct(h.accuracy)}</td>
                      <td className="px-3 py-2 text-right">
                        <Button variant="ghost" size="icon" aria-label={`Remove ${h.name} from ground truth`}
                          disabled={remove.isPending} onClick={() => confirm(`Remove "${h.name}" from ground truth?`) && remove.mutate(h.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {!!q.data.labelers.length && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold">Labeler accuracy</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">How closely each labeler matched the hidden answer key.</p>
              <div className="mt-2 overflow-x-auto" role="region" aria-label="Labeler accuracy table" tabIndex={0}>
                <table className="w-full min-w-[360px] text-sm">
                  <caption className="sr-only">Labeler accuracy on ground-truth images</caption>
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th scope="col" className="py-1.5 font-medium">Labeler</th>
                      <th scope="col" className="py-1.5 text-right font-medium">Attempts</th>
                      <th scope="col" className="py-1.5 text-right font-medium">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.labelers.map((l) => (
                      <tr key={l.user_id} className="border-b last:border-0">
                        <th scope="row" className="py-1.5 text-left font-normal">{l.name}</th>
                        <td className="py-1.5 text-right tabular-nums">{l.attempts}</td>
                        <td className="py-1.5 text-right tabular-nums">{pct(l.accuracy)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
