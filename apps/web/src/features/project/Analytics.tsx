import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, PageHeader, Spinner, Stat } from '@/components/ui'
import { useProject } from './ProjectLayout'

function ChartCard({ title, data, x, y = 'images', color = 'hsl(263 70% 50%)' }: { title: string; data: any[]; x: string; y?: string; color?: string }) {
  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      <div className="h-56">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ left: -16 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="hsl(220 13% 91%)" />
            <XAxis dataKey={x} tick={{ fontSize: 11 }} interval={0} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip cursor={{ fill: 'hsl(251 91% 95%)' }} />
            <Bar dataKey={y} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export default function Analytics() {
  const { project, ws } = useProject()
  const q = useQuery({ queryKey: ['analytics', ws, project.slug], queryFn: () => api.analytics(ws, project.slug) })
  if (!q.data) return <div className="p-10 text-center"><Spinner /></div>
  const a = q.data
  const max = Math.max(1, ...a.heatmap.flat())
  return (
    <div className="anim-page">
      <PageHeader title="Dataset Health Check" desc="Class balance, image sizes and where objects sit in the frame." />
      <div className="space-y-4 px-8 pb-10">
        <div className="grid gap-3 md:grid-cols-4">
          <Stat label="Images" value={a.images} sub={`${a.null_images} without annotations`} />
          <Stat label="Annotations" value={a.annotations} sub={`${a.avg_annotations} per image`} />
          <Stat label="Average size" value={`${a.avg_width}×${a.avg_height}`} sub={`median ${a.median_size}`} />
          <Stat label="Classes" value={a.classes.length} sub={`imbalance ${a.imbalance_ratio}×`} />
        </div>
        {a.imbalance_ratio > 5 && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
            <AlertTriangle className="h-4 w-4" /> The most common class has {a.imbalance_ratio}× more labels than the rarest — consider collecting more of the under-represented classes.
          </div>
        )}
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Class balance</h3>
          <div className="space-y-2">
            {a.classes.map((c) => {
              const top = a.classes[0]?.count || 1
              return (
                <div key={c.id} className="flex items-center gap-3 text-sm">
                  <span className="w-36 truncate">{c.name}</span>
                  <div className="h-5 flex-1 overflow-hidden rounded bg-muted"><div className="h-full rounded" style={{ width: `${(c.count / top) * 100}%`, background: c.color }} /></div>
                  <span className="w-14 text-right tabular-nums text-muted-foreground">{c.count}</span>
                  {c.count < top * 0.2 && <span className="text-[11px] font-semibold text-amber-700">under-represented</span>}
                </div>
              )
            })}
          </div>
        </Card>
        <div className="grid gap-4 lg:grid-cols-3">
          <ChartCard title="Annotations per image" data={a.annotations_per_image} x="n" />
          <ChartCard title="Image size" data={a.sizes} x="bucket" color="hsl(224 76% 48%)" />
          <ChartCard title="Aspect ratio" data={a.aspect} x="bucket" color="hsl(142 72% 29%)" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-4">
            <h3 className="mb-3 text-sm font-semibold">Annotation heatmap <span className="font-normal text-muted-foreground">(object centres)</span></h3>
            <div className="mx-auto grid aspect-video max-w-md grid-cols-10 gap-0.5 rounded border bg-muted p-0.5">
              {a.heatmap.flat().map((v, i) => <div key={i} title={`${v}`} style={{ background: `hsl(263 70% 50% / ${v / max})` }} className="rounded-sm" />)}
            </div>
          </Card>
          <Card className="p-4 text-sm">
            <h3 className="mb-3 font-semibold">Splits & status</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>{Object.entries(a.splits).map(([k, v]) => <div key={k} className="flex justify-between border-b py-1.5"><span className="capitalize">{k}</span><b>{v}</b></div>)}</div>
              <div>{Object.entries(a.statuses).map(([k, v]) => <div key={k} className="flex justify-between border-b py-1.5"><span className="capitalize">{k === 'done' ? 'dataset' : k}</span><b>{v}</b></div>)}</div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
