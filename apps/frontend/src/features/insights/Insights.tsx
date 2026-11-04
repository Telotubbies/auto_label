import { useSearchParams } from 'react-router-dom'
import { PageHeader, Tabs } from '@/components/ui'
import { useProject } from '../project/ProjectLayout'
import { CompareTab } from './CompareTab'
import { EvaluationTab } from './EvaluationTab'
import { TrainingTab } from './TrainingTab'

const TABS = [
  { id: 'training', label: 'Training' },
  { id: 'evaluation', label: 'Evaluation' },
  { id: 'compare', label: 'Compare' },
]

export default function Insights() {
  const { project, ws } = useProject()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = TABS.some((t) => t.id === requested) ? requested! : 'training'
  const modelParam = params.get('model') ?? undefined

  const changeTab = (id: string) => {
    const next = new URLSearchParams(params)
    next.set('tab', id)
    setParams(next, { replace: true })
  }

  return (
    <div className="anim-page">
      <PageHeader title="Insights" desc="Training curves, evaluation diagnostics and model comparisons, all in one place." />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <Tabs tabs={TABS} active={tab} onChange={changeTab} />
        {tab === 'training' ? <TrainingTab ws={ws} slug={project.slug} modelParam={modelParam} />
          : tab === 'evaluation' ? <EvaluationTab ws={ws} slug={project.slug} modelParam={modelParam} />
            : <CompareTab ws={ws} slug={project.slug} modelParam={modelParam} />}
      </div>
    </div>
  )
}
