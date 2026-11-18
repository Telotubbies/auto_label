import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Cpu, Copy, Radio, Server } from 'lucide-react'
import { Card, Tabs, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { projectPath } from '@/lib/routes'
import { useFlag } from '@/lib/flags'
import { INSTALL, deploySnippet, type DeployKind, type DeployLang } from './deploySnippets'

function Code({ text }: { text: string }) {
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-lg bg-sidebar p-4 pr-12 font-mono text-xs text-sidebar-foreground">{text}</pre>
      <button className="absolute right-2 top-2 cursor-pointer rounded p-1 text-sidebar-foreground/70 hover:text-white" onClick={() => { navigator.clipboard.writeText(text); toast.ok('Copied') }} aria-label="Copy code"><Copy className="h-4 w-4" /></button>
    </div>
  )
}

const Step = ({ n, title, children }: { n: number; title: string; children: React.ReactNode }) => (
  <li className="flex gap-3">
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{n}</span>
    <div className="min-w-0 flex-1 space-y-2"><h4 className="text-sm font-semibold">{title}</h4>{children}</div>
  </li>
)

/** Left list of the ways to deploy the selected model, right = numbered steps for the hosted API. */
export function Deployments({ ws, project, endpoint }: { ws: string; project: string; endpoint: string }) {
  const streams = useFlag('task_10b')
  const [opt, setOpt] = useState('api')
  const [kind, setKind] = useState<DeployKind>('images')
  const [lang, setLang] = useState<DeployLang>('python')
  const options: { id: string; label: string; icon: typeof Server; to?: string; hint?: string }[] = [
    { id: 'api', label: 'Hosted API', icon: Server },
    ...(streams ? [{ id: 'stream', label: 'Streaming', icon: Radio, to: projectPath(ws, project, 'deploy?tab=streams'), hint: 'Run the model on a live camera or RTSP stream.' }] : []),
    { id: 'edge', label: 'Edge export', icon: Cpu, to: projectPath(ws, project, 'models'), hint: 'Build a device-targeted package from the model page.' },
    { id: 'self', label: 'Self-hosted weights', icon: Boxes, to: projectPath(ws, project, 'models'), hint: 'Download the weights from the model page and run them yourself.' },
  ]
  const cur = options.find((o) => o.id === opt) ?? options[0]
  return (
    <section aria-label="Deployments" className="grid gap-6 px-8 pb-10 lg:grid-cols-[14rem_1fr]">
      <Card className="h-fit p-1.5">
        <h3 className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Deploy</h3>
        {options.map((o) => (
          <button key={o.id} data-testid={`deploy-opt-${o.id}`} onClick={() => setOpt(o.id)} aria-pressed={opt === o.id}
            className={cn('flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-left text-sm', opt === o.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}>
            <o.icon className="h-4 w-4" /> {o.label}
          </button>
        ))}
      </Card>
      <Card className="p-5">
        {cur.to ? (
          <div className="text-sm"><h3 className="mb-1 font-semibold">{cur.label}</h3><p className="mb-3 text-muted-foreground">{cur.hint}</p>
            <Link to={cur.to} className="text-primary hover:underline">Open {cur.label.toLowerCase()}</Link></div>
        ) : (
          <ol className="space-y-5">
            <Step n={1} title="Install the library"><Code text={INSTALL[lang]} /></Step>
            <Step n={2} title="Copy and run the code">
              <Tabs tabs={[{ id: 'images', label: 'Images' }, { id: 'video', label: 'Video' }]} active={kind} onChange={(k) => setKind(k as DeployKind)} />
              <Tabs tabs={[{ id: 'python', label: 'Python' }, { id: 'javascript', label: 'JavaScript' }, { id: 'curl', label: 'cURL' }]} active={lang} onChange={(l) => setLang(l as DeployLang)} />
              <Code text={deploySnippet(kind, lang, endpoint)} />
            </Step>
          </ol>
        )}
      </Card>
    </section>
  )
}
