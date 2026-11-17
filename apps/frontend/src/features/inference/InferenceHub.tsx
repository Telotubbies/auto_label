import { useState } from 'react'
import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Glass } from '@/components/glass'
import { Button, PageHeader, Select, Spinner, Tabs } from '@/components/ui'
import { inferenceApi } from '@/lib/api/inference'
import { useWorkspaceFlags } from '@/lib/flags'
import { useApp } from '@/lib/store'
import { INFERENCE_TAB_LABELS, INFERENCE_TABS, tabFrom, type InferenceTab } from './tabs.ts'
import CalculatorTab from './CalculatorTab'
import EnginesTab from './EnginesTab'
import ModelsTab from './ModelsTab'
import SegmentationTab from './SegmentationTab'

/**
 * `/:ws/inference` — one page under the `task_inference` flag. The header owns the host picker for
 * every tab; the panels arrive with their own cards.
 *
 * PLAN §12.5: any workspace member reads the Calculator, which touches no host. The other three
 * surfaces install and download on a host, so they stay admin work — a member gets the Calculator
 * alone, with no host picker (the picker reads the admin-only `/hosts`).
 */
export default function InferenceHub() {
  const { ws = '' } = useParams()
  const flags = useWorkspaceFlags()
  const role = useApp((s) => s.role)
  const staff = role === 'owner' || role === 'admin'
  const [params, setParams] = useSearchParams()
  const tab = staff ? tabFrom(params.toString()) : 'calculator'
  const hosts = useQuery({
    queryKey: ['inference-hosts', ws],
    queryFn: () => inferenceApi.hosts(ws),
    enabled: !!ws && staff,
    staleTime: 15_000,
    refetchInterval: 30_000,
  })
  const [hostId, setHostId] = useState('')
  const list = hosts.data?.hosts ?? []
  // Default: the first online host with a GPU (PLAN §4.1), else the first host the workspace lists.
  const host = list.find((row) => row.id === hostId)
    ?? list.find((row) => row.online && (row.inventory?.gpus?.length ?? 0) > 0)
    ?? list[0] ?? null

  // A shared link must not bounce to the workspace index while the flag query is in flight.
  if (flags.isLoading) {
    return <div className="flex h-40 items-center justify-center text-muted-foreground"><Spinner /></div>
  }
  if (!flags.data?.enabled.includes('task_inference')) return <Navigate to={`/${ws}`} replace />

  // Replace, not push: the tab is a view of one page, so Back leaves the hub instead of walking tabs.
  const changeTab = (id: string) => {
    const next = new URLSearchParams(params)
    next.set('tab', id)
    setParams(next, { replace: true })
  }
  const tabs: readonly InferenceTab[] = staff ? INFERENCE_TABS : ['calculator']

  return (
    <div className="anim-page">
      <PageHeader
        title="Inference"
        desc={staff
          ? 'Install inference engines, download models and size them against this host.'
          : 'Size a model against a card. Nothing is installed or downloaded from here.'}
        actions={
          staff && (
            <div className="w-full sm:w-auto">
              {hosts.isError ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-destructive">Hosts did not load.</span>
                  <Button variant="outline" size="sm" onClick={() => void hosts.refetch()}>Retry</Button>
                </div>
              ) : hosts.isLoading ? (
                <div className="h-9 w-full sm:w-56" role="status" aria-label="Loading hosts">
                  <div aria-hidden className="h-9 w-full animate-pulse rounded-md bg-muted" />
                </div>
              ) : (
                <Select aria-label="Host" className="w-full sm:w-56" value={host?.id ?? ''}
                  disabled={!list.length} onChange={(e) => setHostId(e.target.value)}>
                  {!list.length && <option value="">No host has reported</option>}
                  {list.map((row) => (
                    <option key={row.id} value={row.id}>{row.host}{row.online ? '' : ' (offline)'}</option>
                  ))}
                </Select>
              )}
            </div>
          )
        }
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <Glass className="rounded-xl p-2">
          <div className="hidden sm:block">
            <Tabs tabs={tabs.map((id) => ({ id, label: INFERENCE_TAB_LABELS[id] }))}
              active={tab} onChange={changeTab} />
          </div>
          <div className="sm:hidden">
            <Select aria-label="Inference section" className="w-full" value={tab}
              onChange={(e) => changeTab(e.target.value)}>
              {tabs.map((id) => <option key={id} value={id}>{INFERENCE_TAB_LABELS[id]}</option>)}
            </Select>
          </div>
        </Glass>
        {tab === 'calculator' ? <CalculatorTab /> : tab === 'engines' ? (
          <EnginesTab ws={ws} host={host} hostsLoading={hosts.isLoading} hostsError={hosts.isError}
            onRetryHosts={() => void hosts.refetch()} />
        ) : tab === 'models' ? (
          <ModelsTab ws={ws} host={host} hostsLoading={hosts.isLoading} hostsError={hosts.isError}
            onRetryHosts={() => void hosts.refetch()} />
        ) : (
          <SegmentationTab ws={ws} host={host} hostsLoading={hosts.isLoading} hostsError={hosts.isError}
            onRetryHosts={() => void hosts.refetch()} />
        )}
      </div>
    </div>
  )
}
