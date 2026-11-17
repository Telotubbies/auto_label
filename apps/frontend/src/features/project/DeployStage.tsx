import { lazy } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFlag } from '@/lib/flags'
import { resolveTab } from '@/lib/nav/project/stages.ts'
import { FlagGate, PermGate } from '@/routes/guards'
import StageTabs from '@/components/shell/StageTabs'

const Deploy = lazy(() => import('./Deploy'))
const Streams = lazy(() => import('@/features/streams/Streams'))

/** Test first, Streams second; the endpoint card lives inside Test (S10). */
const PANES = {
  test: <PermGate perm="project.models"><Deploy /></PermGate>,
  streams: <FlagGate flag="task_10b"><PermGate perm="project.streams"><Streams /></PermGate></FlagGate>,
}

export default function DeployStage() {
  const [sp] = useSearchParams()
  const v3 = useFlag('task_470')
  if (!v3) return <PermGate perm="project.models"><Deploy /></PermGate>
  const tab = resolveTab('deploy', sp.get('tab')) as keyof typeof PANES
  return <StageTabs stage="deploy">{PANES[tab] ?? PANES.test}</StageTabs>
}
