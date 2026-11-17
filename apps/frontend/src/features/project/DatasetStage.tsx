import { lazy } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFlag } from '@/lib/flags'
import { resolveTab } from '@/lib/nav/project/stages.ts'
import { PermGate } from '@/routes/guards'
import StageTabs from '@/components/shell/StageTabs'
import Dataset from './Dataset'

const Versions = lazy(() => import('./Versions'))
const DatasetHealth = lazy(() => import('./DatasetHealth').then((m) => ({ default: m.DatasetHealth })))

/** The three dataset sub-surfaces; the tab row is the only entry, and each pane keeps its gate. */
const PANES = {
  images: <Dataset />,
  versions: <PermGate perm="project.export"><Versions /></PermGate>,
  health: <PermGate perm="project.review"><DatasetHealth /></PermGate>,
}

export default function DatasetStage() {
  const [sp] = useSearchParams()
  const v3 = useFlag('task_470')
  if (!v3) return <Dataset />
  const tab = resolveTab('dataset', sp.get('tab')) as keyof typeof PANES
  return <StageTabs stage="dataset">{PANES[tab] ?? PANES.images}</StageTabs>
}
