import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { Glass } from '@/components/glass'
import { Card, EmptyState, PageHeader, Select, Spinner, Tabs } from '@/components/ui'
import { useWorkspaceFlags } from '@/lib/flags'
import { INFERENCE_TAB_LABELS, INFERENCE_TABS, tabFrom, type InferenceTab } from './tabs.ts'
import CalculatorTab from './CalculatorTab'

/** Each panel is a real empty state until its own card lands; the calculator has its own screen. */
const PANEL_EMPTY: Record<Exclude<InferenceTab, 'calculator'>, string> = {
  engines: 'No engine catalogue yet.',
  models: 'No model catalogue yet.',
  segmentation: 'No segmentation model is provisioned on this host.',
}

/**
 * `/:ws/inference` — one admin-only page under the `task_inference` flag. The host picker, the
 * catalogues, the calculator and the segmentation cards arrive with their own cards; this shell
 * owns the header, the host-picker slot, the four tabs and the URL-synced selection.
 */
export default function InferenceHub() {
  const { ws = '' } = useParams()
  const flags = useWorkspaceFlags()
  const [params, setParams] = useSearchParams()
  const tab = tabFrom(params.toString())

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

  return (
    <div className="anim-page">
      <PageHeader
        title="Inference"
        desc="Install inference engines, download models and size them against this host."
        actions={
          <div className="w-full sm:w-auto">
            {/* T-1001 fills this picker; until a worker reports, its one honest value is "none". */}
            <Select aria-label="Host" disabled className="w-full sm:w-56" defaultValue="none">
              <option value="none">No host has reported</option>
            </Select>
          </div>
        }
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <Glass className="rounded-xl p-2">
          <div className="hidden sm:block">
            <Tabs tabs={INFERENCE_TABS.map((id) => ({ id, label: INFERENCE_TAB_LABELS[id] }))}
              active={tab} onChange={changeTab} />
          </div>
          <div className="sm:hidden">
            <Select aria-label="Inference section" className="w-full" value={tab}
              onChange={(e) => changeTab(e.target.value)}>
              {INFERENCE_TABS.map((id) => <option key={id} value={id}>{INFERENCE_TAB_LABELS[id]}</option>)}
            </Select>
          </div>
        </Glass>
        {tab === 'calculator' ? <CalculatorTab /> : (
          <Card className="p-4 sm:p-6">
            <h2 className="text-sm font-medium">{INFERENCE_TAB_LABELS[tab]}</h2>
            <EmptyState title={PANEL_EMPTY[tab]} />
          </Card>
        )}
      </div>
    </div>
  )
}
