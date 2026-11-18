import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Download, Package } from 'lucide-react'
import { api, ApiError, fileUrl, post } from '@/lib/api'
import type { ModelItem } from '@/lib/types'
import { Badge, Button, Card, Field, Progress, Select, Spinner, toast } from '@/components/ui'
import { artifactLabel, buildBody, pickDtype } from './edgeDtype'

/** Download sizes for deployment artifacts, compared in decimal GB, so this keeps its own rule. */
const fmtPackageBytes = (n: number) =>
  n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n >= 1e3 ? `${Math.round(n / 1e3)} KB` : `${n} B`

/** Task 34: build a device-targeted export preset and download its zip. */
export default function EdgeExport({ ws, project, model }: { ws: string; project: string; model: ModelItem }) {
  const qc = useQueryClient()
  const [picked, setPicked] = useState('')
  const [pickedDtype, setPickedDtype] = useState('')
  const presets = useQuery({
    queryKey: ['edge-presets', ws, project],
    queryFn: () => api.edgePresets(ws, project),
    retry: false, // 404 means the flag is off, not a transient failure
  })
  const jobs = useQuery({
    queryKey: ['edge-jobs', ws, project],
    queryFn: () => api.jobs(ws, project, 'export_preset'),
    enabled: presets.isSuccess,
    refetchInterval: (q) => (q.state.data?.some((j) => ['queued', 'running'].includes(j.status)) ? 2500 : false),
  })

  const list = presets.data ?? []
  const preset = list.find((p) => p.id === picked) ?? list[0]
  const dtype = pickDtype(preset, pickedDtype)
  const modelJobs = (jobs.data ?? []).filter((j) => j.params.model_id === model.id)
  const building = modelJobs.find((j) => ['queued', 'running'].includes(j.status))
  const failed = building ? undefined : modelJobs.find((j) => j.params.preset === preset?.id && j.status === 'failed')
  const built = Object.entries(model.edgeExports ?? {})
  const labelOf = (key: string) => artifactLabel(list, key)
  const runningLabel = building?.params.preset
    ? labelOf(building.params.dtype ? `${building.params.preset}:${building.params.dtype}` : String(building.params.preset))
    : 'preset'
  const builtKey = preset ? (dtype && dtype !== preset.dtypes?.find((d) => d.default)?.id ? `${preset.id}:${dtype}` : preset.id) : ''

  // The build runs outside the model row, so pull the artifact in once the job is done.
  const doneIds = modelJobs.filter((j) => j.status === 'done').map((j) => j.id).join(',')
  const prevDoneIds = useRef(doneIds)
  useEffect(() => {
    if (prevDoneIds.current !== doneIds) {
      qc.invalidateQueries({ queryKey: ['model', ws, project, model.id] })
      qc.invalidateQueries({ queryKey: ['models', ws, project] })
    }
    prevDoneIds.current = doneIds
  }, [doneIds, qc, ws, project, model.id])

  const build = () => {
    if (!preset) return
    post(`${api.P(ws, project)}/models/${model.id}/export`, buildBody(preset, dtype))
      .then(() => {
        toast.ok(`${labelOf(builtKey)} build queued`)
        qc.invalidateQueries({ queryKey: ['edge-jobs', ws, project] })
      })
      .catch(toast.err)
  }

  const chosen = preset?.dtypes?.find((d) => d.id === dtype)
  const dtypeHint = chosen?.needs_data ? "INT8 calibrates on images from this model's dataset." : (preset?.dtypes?.length ?? 0) < 2 ? 'This preset builds one type.' : undefined

  if (presets.isLoading) return <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Spinner /> Loading edge presets…</Card>
  // Flag off answers 404: show nothing rather than a broken panel.
  if (presets.isError) {
    if (presets.error instanceof ApiError && presets.error.status === 404) return null
    return (
      <Card role="alert" className="flex flex-wrap items-center gap-2 p-4 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0 text-warning" /> Edge presets could not be loaded.
        <Button size="sm" variant="outline" onClick={() => presets.refetch()}>Retry</Button>
      </Card>
    )
  }
  if (!list.length) return <Card className="p-4 text-sm text-muted-foreground">No edge export presets are available for this model.</Card>

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Edge export</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Each preset builds a zip with the model and its runtime files.</p>
        </div>
        {presets.isFetching && <Spinner className="h-4 w-4 text-muted-foreground" />}
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="sm:w-72">
          <Field label="Preset">
            <Select className="w-full" value={preset?.id ?? ''} onChange={(e) => { setPicked(e.target.value); setPickedDtype('') }} disabled={!preset}>
              {list.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </Select>
          </Field>
        </div>
        <div className="sm:w-52">
          <Field label="Data type" hint={dtypeHint}>
            <Select className="w-full" value={dtype} onChange={(e) => setPickedDtype(e.target.value)} disabled={!preset || (preset.dtypes?.length ?? 0) < 2}>
              {(preset?.dtypes ?? []).map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
            </Select>
          </Field>
        </div>
        <Button variant="outline" className="w-full sm:w-auto" disabled={!!building || !preset} onClick={build}>
          {building
            ? <><Spinner className="h-3.5 w-3.5" /> Building…</>
            : <><Package className="h-4 w-4" /> {model.edgeExports?.[builtKey] ? 'Rebuild' : 'Build'}</>}
        </Button>
      </div>
      {preset?.hint && <p className="mt-1.5 text-xs text-muted-foreground">{preset.hint}</p>}
      {!preset?.verified && (
        <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Badge className="border border-warning/40 bg-warning/10 text-warning"
            title="This preset has not been executed on the real device, so its compatibility is unconfirmed.">
            UNVERIFIED
          </Badge>
          Not yet run on the target device.
        </p>
      )}
      {preset?.device && <p className="text-xs text-muted-foreground">Targets: {preset.device}</p>}
      {preset?.requires && <p className="text-xs text-muted-foreground">Requires: {preset.requires}</p>}

      {building && (
        <div className="mt-3">
          <div className="mb-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{building.status === 'queued' ? 'Waiting for a worker…' : `Building ${runningLabel}…`}</span>
            <span className="tabular-nums">{Math.round(building.progress ?? 0)}%</span>
          </div>
          <Progress value={building.progress ?? 0} />
        </div>
      )}

      {failed && (
        <div role="alert" className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <p className="font-medium">Build failed</p>
          <p className="mt-0.5 break-words text-muted-foreground">{failed.error || 'See worker logs for details.'}</p>
        </div>
      )}

      {built.length ? (
        <>
          <ul className="mt-3 divide-y rounded-md border" aria-label="Built edge exports">
            {built.map(([id, artifact]) => (
              <li key={id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-medium">{labelOf(id)}</span>
                    {!artifact.verified && (
                      <Badge className="border border-warning/40 bg-warning/10 text-warning"
                        title="Built but not executed on the real device, so its compatibility is unconfirmed.">
                        UNVERIFIED<span className="sr-only">: not executed on the real device</span>
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {fmtPackageBytes(artifact.bytes)}{artifact.device ? ` on ${artifact.device}` : ''}
                  </p>
                </div>
                <a href={fileUrl(artifact.url)}>
                  <Button variant="outline" size="sm">
                    <Download className="h-3.5 w-3.5" /> Download<span className="sr-only"> {labelOf(id)} zip</span>
                  </Button>
                </a>
              </li>
            ))}
          </ul>
          {built.some(([, a]) => !a.verified) && (
            <p className="mt-2 text-xs text-muted-foreground">UNVERIFIED means the zip was built but never run on the target device.</p>
          )}
        </>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">Nothing built yet. Pick a preset and build to get a zip download.</p>
      )}
    </Card>
  )
}
