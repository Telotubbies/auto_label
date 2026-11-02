import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Copy, Download, LayoutDashboard, Link2, Loader2, Plus, Save, Share2, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button, Card, Dropdown, EmptyState, Input, Modal, PageHeader, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { ErrorState, PageSkeleton, toCsv, useChartTheme } from '@/features/insights/charts'
import { useProject } from '../project/ProjectLayout'
import { WidgetCard } from './WidgetCard'
import { WidgetEditor, type WidgetRefs } from './WidgetEditor'
import { dashboardCsv, defaultWidget, moveWidget, type WidgetSpec } from './widgetModel'
import { fetchWidget, useWidgetQueries, useWidgetRefs, widgetQueryKey } from './useWidgetData'
import { exportDashboardPng } from './dashboardExport'

const SPAN: Record<number, string> = { 3: 'lg:col-span-3', 4: 'lg:col-span-4', 6: 'lg:col-span-6', 12: 'lg:col-span-12' }

function saveFile(name: string, data: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

function fileStem(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'dashboard'
}

export default function DashboardEditor() {
  const { ws, project } = useProject()
  const { id, token } = useParams()
  const slug = project.slug
  const readOnly = !!token
  const navigate = useNavigate()
  const qc = useQueryClient()
  const theme = useChartTheme()
  const refs: WidgetRefs = useWidgetRefs(ws, slug, !readOnly)

  const [local, setLocal] = useState<WidgetSpec[] | null>(null)
  const [nameDraft, setNameDraft] = useState<string | null>(null)
  const [draft, setDraft] = useState<WidgetSpec | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState<'csv' | 'png' | null>(null)

  useEffect(() => {
    setLocal(null); setNameDraft(null); setDraft(null); setConfirmDelete(false)
  }, [id, token])

  const dash = useQuery({
    queryKey: readOnly ? ['dashboard-shared', ws, slug, token] : ['dashboard', ws, slug, id],
    queryFn: () => readOnly
      ? api.sharedDashboard(ws, slug, token!)
      : api.dashboard(ws, slug, id!),
    enabled: readOnly ? !!token : !!id,
  })

  const saved = useMemo<WidgetSpec[]>(() => (dash.data?.widgets ?? []) as WidgetSpec[], [dash.data])
  const widgets = local ?? saved
  const name = nameDraft ?? dash.data?.name ?? ''
  const dirty = local !== null || nameDraft !== null
  const queries = useWidgetQueries(ws, slug, widgets)

  const save = useMutation({
    mutationFn: () => {
      if (!id) throw new Error('This dashboard is read-only.')
      if (!name.trim()) throw new Error('Give the dashboard a name.')
      return api.updateDashboard(ws, slug, id, { name: name.trim(), widgets })
    },
    onSuccess: (next) => {
      setLocal(null); setNameDraft(null)
      qc.setQueryData(['dashboard', ws, slug, id], next)
      qc.invalidateQueries({ queryKey: ['dashboards', ws, slug] })
      toast.ok('Dashboard saved')
    },
    onError: (e) => toast.err(e as Error),
  })

  const share = useMutation({
    mutationFn: () => api.shareDashboard(ws, slug, id!),
    onSuccess: (link) => {
      qc.invalidateQueries({ queryKey: ['dashboard', ws, slug, id] })
      toast.ok('Share link ready — anyone in the workspace can view it.')
      const url = `${window.location.origin}/${ws}/${slug}/dashboards/shared/${link.token}`
      navigator.clipboard?.writeText(url).catch(() => undefined)
    },
    onError: (e) => toast.err(e as Error),
  })

  const remove = useMutation({
    mutationFn: () => api.deleteDashboard(ws, slug, id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dashboards', ws, slug] })
      toast.ok('Dashboard deleted')
      navigate(`/${ws}/${slug}/dashboards`)
    },
    onError: (e) => toast.err(e as Error),
  })

  const shareToken = dash.data?.share_token ?? ''
  const shareUrl = shareToken ? `${window.location.origin}/${ws}/${slug}/dashboards/shared/${shareToken}` : ''

  const gather = async () => {
    const datas = await Promise.all(widgets.map((spec) => qc.fetchQuery({
      queryKey: widgetQueryKey(ws, slug, spec),
      queryFn: () => fetchWidget(ws, slug, spec),
      staleTime: 60_000,
    })))
    return widgets.map((spec, i) => ({ spec, data: datas[i] }))
  }

  const exportCsv = async () => {
    setBusy('csv')
    try {
      const items = await gather()
      const rows = dashboardCsv(items.map((item) => ({ title: item.spec.title, data: item.data })))
      saveFile(`${fileStem(name)}.csv`, toCsv(rows), 'text/csv;charset=utf-8')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(null)
    }
  }

  const exportPng = async () => {
    setBusy('png')
    try {
      const items = await gather()
      await exportDashboardPng(name, items, theme)
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(null)
    }
  }

  const addWidget = () => setDraft({
    ...defaultWidget('dataset'),
    id: `w${Date.now().toString(36)}`,
    title: 'New widget',
  })

  const saveWidget = (spec: WidgetSpec) => {
    setLocal((prev) => {
      const list = prev ?? saved
      return list.some((w) => w.id === spec.id)
        ? list.map((w) => (w.id === spec.id ? spec : w))
        : [...list, spec]
    })
    setDraft(null)
  }

  if (dash.isLoading) return <div className="px-4 pt-4 sm:px-8"><PageSkeleton /></div>
  if (dash.isError || !dash.data) {
    return (
      <div className="px-4 pt-4 sm:px-8">
        <ErrorState title="Dashboard could not be loaded" message={(dash.error as Error)?.message} onRetry={() => dash.refetch()} />
      </div>
    )
  }

  return (
    <div className="anim-page">
      <PageHeader
        title={readOnly ? name : (name || 'Untitled dashboard')}
        desc={readOnly ? 'Shared view — read-only, inside this workspace.' : 'Pick a source, a measure and a dimension, then arrange the widgets.'}
        actions={(
          <div className="flex flex-wrap items-center justify-end gap-2">
            {!readOnly && (
              <Button variant="ghost" size="sm" onClick={() => navigate(`/${ws}/${slug}/dashboards`)}>
                <ArrowLeft className="h-4 w-4" /> Dashboards
              </Button>
            )}
            {!readOnly && <Button variant="outline" size="sm" onClick={addWidget}><Plus className="h-4 w-4" /> Add widget</Button>}
            {!readOnly && (
              <Button size="sm" onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
              </Button>
            )}
            {!readOnly && (
              <Button variant="outline" size="sm" onClick={() => share.mutate()} disabled={share.isPending || !id}>
                {share.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Share2 className="h-4 w-4" />} Share
              </Button>
            )}
            <Dropdown
              align="right"
              items={[
                { label: <span className="flex items-center gap-2"><Download className="h-4 w-4" /> Dashboard PNG</span>, onClick: exportPng },
                { label: <span className="flex items-center gap-2"><Download className="h-4 w-4" /> Data CSV</span>, onClick: exportCsv },
              ]}
              trigger={(
                <Button variant="outline" size="sm" disabled={busy !== null || !widgets.length}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Export
                </Button>
              )}
            />
            {!readOnly && (
              <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" aria-label="Delete dashboard" onClick={() => setConfirmDelete(true)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <div className="space-y-4 px-4 pb-10 sm:px-8">
        {!readOnly && (
          <Card className="flex flex-wrap items-end gap-3 p-3">
            <label className="min-w-0 basis-full sm:flex-1">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">Dashboard name</span>
              <Input value={name} maxLength={120} className="h-9 max-w-md"
                onChange={(e) => setNameDraft(e.target.value)} />
            </label>
            <p className="text-xs text-muted-foreground" role="status">
              {dirty ? 'Unsaved changes' : `Saved ${dash.data.updated ? new Date(dash.data.updated * 1000).toLocaleString() : ''}`}
            </p>
          </Card>
        )}

        {shareUrl && !readOnly && (
          <Card className="flex flex-wrap items-center gap-2 p-3">
            <Link2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <label htmlFor="share-link" className="text-xs font-medium">Read-only link</label>
            <Input id="share-link" readOnly value={shareUrl} className="h-8 min-w-0 flex-1 font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
            <Button variant="outline" size="sm" onClick={() => {
              navigator.clipboard?.writeText(shareUrl).then(() => toast.ok('Link copied')).catch(() => toast.err('Could not copy the link'))
            }}><Copy className="h-4 w-4" /> Copy</Button>
          </Card>
        )}

        {widgets.length ? (
          <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 lg:grid-cols-12">
            {widgets.map((spec, index) => (
              <div key={spec.id} className={cn('min-w-0', SPAN[spec.w] ?? 'lg:col-span-6')}>
                <WidgetCard
                  spec={spec}
                  data={queries[index]?.data}
                  loading={queries[index]?.isLoading ?? false}
                  error={(queries[index]?.error as Error)?.message}
                  editable={!readOnly}
                  onEdit={() => setDraft(spec)}
                  onRemove={() => setLocal((prev) => (prev ?? saved).filter((w) => w.id !== spec.id))}
                  onMove={(delta) => setLocal((prev) => moveWidget(prev ?? saved, index, delta))}
                />
              </div>
            ))}
          </div>
        ) : (
          <Card className="p-8">
            <EmptyState
              icon={<LayoutDashboard className="h-8 w-8 text-muted-foreground/50" />}
              title="No widgets yet"
              hint={readOnly ? 'This shared dashboard has no widgets.' : 'Add a chart from the dataset, a version, a model evaluation or stream events.'}
              action={!readOnly ? <Button onClick={addWidget}><Plus className="h-4 w-4" /> Add widget</Button> : undefined}
            />
          </Card>
        )}
      </div>

      {draft && (
        <WidgetEditor
          key={draft.id}
          initial={draft}
          refs={refs}
          onSave={saveWidget}
          onClose={() => setDraft(null)}
        />
      )}

      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete this dashboard?">
        <p className="text-sm text-muted-foreground">
          “{name}” and its {widgets.length} {widgets.length === 1 ? 'widget' : 'widgets'} will be removed. The shared link stops working.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} Delete dashboard
          </Button>
        </div>
      </Modal>
    </div>
  )
}
