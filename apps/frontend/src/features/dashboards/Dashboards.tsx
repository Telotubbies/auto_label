import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, LayoutDashboard, Loader2, Plus, Share2, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button, Card, EmptyState, Field, Input, Modal, PageHeader, toast, fmtAgo } from '@/components/ui'
import { ErrorState, PageSkeleton } from '@/features/insights/charts'
import { useProject } from '../project/ProjectLayout'

export default function Dashboards() {
  const { ws, project } = useProject()
  const slug = project.slug
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(null)

  const list = useQuery({
    queryKey: ['dashboards', ws, slug],
    queryFn: () => api.dashboards(ws, slug),
  })

  const create = useMutation({
    mutationFn: () => api.createDashboard(ws, slug, { name: name.trim(), widgets: [] }),
    onSuccess: (dash) => {
      qc.invalidateQueries({ queryKey: ['dashboards', ws, slug] })
      setCreating(false)
      setName('')
      toast.ok('Dashboard created')
      navigate(`/${ws}/${slug}/dashboards/${dash.id}`)
    },
    onError: (e) => toast.err(e as Error),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteDashboard(ws, slug, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dashboards', ws, slug] })
      setRemoving(null)
      toast.ok('Dashboard deleted')
    },
    onError: (e) => toast.err(e as Error),
  })

  return (
    <div className="anim-page">
      <PageHeader
        title="Dashboards"
        desc="Saved views of dataset, version, model and stream numbers for this project."
        actions={<Button size="sm" onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New dashboard</Button>}
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        {list.isLoading ? <PageSkeleton /> : list.isError ? (
          <ErrorState title="Dashboards could not be loaded" message={(list.error as Error).message} onRetry={() => list.refetch()} />
        ) : !list.data?.length ? (
          <Card className="p-8">
            <EmptyState
              icon={<LayoutDashboard className="h-8 w-8 text-muted-foreground/50" />}
              title="No dashboards yet"
              hint="Build a dashboard from the dataset, a frozen version, a model evaluation or stream events."
              action={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New dashboard</Button>}
            />
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {list.data.map((dash) => (
              <Card key={dash.id} className="flex min-w-0 flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold">{dash.name}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {dash.widgets.length} {dash.widgets.length === 1 ? 'widget' : 'widgets'} · updated {fmtAgo(dash.updated)}
                    </p>
                  </div>
                  {dash.share_token ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground">
                      <Share2 className="h-3 w-3" aria-hidden="true" /> Shared
                    </span>
                  ) : null}
                </div>
                <div className="mt-auto flex items-center gap-2 pt-4">
                  <Button size="sm" onClick={() => navigate(`/${ws}/${slug}/dashboards/${dash.id}`)}>
                    Open <ArrowRight className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="ml-auto h-8 w-8 text-destructive"
                    aria-label={`Delete ${dash.name}`} onClick={() => setRemoving({ id: dash.id, name: dash.name })}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal open={creating} onClose={() => setCreating(false)} title="New dashboard">
        <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate() }}>
          <Field label="Name" hint="You can add widgets and rename it on the next screen.">
            <Input value={name} maxLength={120} autoFocus placeholder="Ops overview"
              onChange={(e) => setName(e.target.value)} />
          </Field>
          <div className="mt-4 flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setCreating(false)}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!removing} onClose={() => setRemoving(null)} title="Delete this dashboard?">
        <p className="text-sm text-muted-foreground">
          “{removing?.name}” and its widgets will be removed. A shared link stops working.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setRemoving(null)}>Cancel</Button>
          <Button variant="destructive" disabled={remove.isPending}
            onClick={() => removing && remove.mutate(removing.id)}>
            {remove.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} Delete
          </Button>
        </div>
      </Modal>
    </div>
  )
}
