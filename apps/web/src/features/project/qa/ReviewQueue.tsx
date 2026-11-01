import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, fileUrl } from '@/lib/api'
import { Button, Card, EmptyState } from '@/components/ui'
import { ErrorNote, Loading, pct } from './shared'

export default function ReviewQueue({ ws, slug }: { ws: string; slug: string }) {
  const nav = useNavigate()
  const q = useQuery({ queryKey: ['labeling-review-queue', ws, slug], queryFn: () => api.labelingReviewQueue(ws, slug) })
  if (q.isLoading) return <Loading />
  if (q.isError) return <ErrorNote error={q.error} />
  const items = q.data?.items ?? []
  if (!items.length) {
    return <Card className="p-4"><EmptyState title="Review queue is empty." hint="An image enters the queue once several labelers submit disagreeing annotations." /></Card>
  }
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto" role="region" aria-label="Review queue table" tabIndex={0}>
        <table className="w-full min-w-[720px] text-sm">
          <caption className="px-3 pt-3 text-left text-xs text-muted-foreground">
            Sorted by disagreement, highest first — the images most worth a reviewer’s time.
          </caption>
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <th scope="col" className="w-20 px-3 py-2 font-medium"><span className="sr-only">Preview</span></th>
              <th scope="col" className="px-3 py-2 font-medium">Image</th>
              <th scope="col" className="px-3 py-2 font-medium">Disagreement</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Submissions</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Annotations</th>
              <th scope="col" className="px-3 py-2 text-right font-medium"><span className="sr-only">Action</span></th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.image_id} className="border-b last:border-0">
                <td className="px-3 py-2">
                  <img src={fileUrl(it.thumbnail)} alt="" loading="lazy" className="h-10 w-16 rounded border bg-muted object-cover" />
                </td>
                <th scope="row" className="max-w-[22ch] px-3 py-2 text-left font-medium">
                  <span className="block truncate">{it.name}</span>
                  <span className="text-[11px] font-normal capitalize text-muted-foreground">{it.status}</span>
                </th>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                      <span className="block h-full rounded-full bg-warning" style={{ width: `${Math.min(100, it.disagreement * 100)}%` }} />
                    </span>
                    <span className="tabular-nums">{pct(it.disagreement)}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{it.submissions}</td>
                <td className="px-3 py-2 text-right tabular-nums">{it.annotations}</td>
                <td className="px-3 py-2 text-right">
                  <Button size="sm" variant="outline"
                    onClick={() => nav(`/${ws}/${slug}/images/${it.image_id}?status=review&review=true`)}>Review</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
