import { Fragment, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Printer } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { Badge, Button, Card, PageHeader, Spinner, fmtDate } from '@/components/ui'

type Block =
  | { kind: 'heading'; level: 2 | 3 | 4; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'quote'; text: string }
  | { kind: 'code'; text: string }

/**
 * Tiny Markdown block parser for the DPA template. It renders React elements only —
 * never dangerouslySetInnerHTML — so a compromised template cannot inject markup.
 */
function parseMarkdown(md: string): Block[] {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let code: string[] | null = null

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ kind: 'paragraph', text: paragraph.join(' ') })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push({ kind: 'list', ordered: list.ordered, items: list.items })
    list = null
  }
  const flush = () => { flushParagraph(); flushList() }

  for (const line of lines) {
    if (code) {
      if (line.trim().startsWith('```')) { blocks.push({ kind: 'code', text: code.join('\n') }); code = null } else code.push(line)
      continue
    }
    if (line.trim().startsWith('```')) { flush(); code = []; continue }
    if (!line.trim()) { flush(); continue }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      flush()
      const level = Math.min(4, Math.max(2, heading[1].length + 1)) as 2 | 3 | 4
      blocks.push({ kind: 'heading', level, text: heading[2] })
      continue
    }
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+\.\s+(.*)$/.exec(line)
    if (bullet || numbered) {
      flushParagraph()
      const ordered = !!numbered
      if (list && list.ordered !== ordered) flushList()
      if (!list) list = { ordered, items: [] }
      list.items.push((bullet ?? numbered)?.[1] ?? '')
      continue
    }
    // Wrapped continuation of the previous list item (Markdown wraps at ~100 columns).
    if (list && /^\s{2,}\S/.test(line)) {
      list.items[list.items.length - 1] += ` ${line.trim()}`
      continue
    }
    if (/^\s*>\s?/.test(line)) {
      flush()
      blocks.push({ kind: 'quote', text: line.replace(/^\s*>\s?/, '') })
      continue
    }
    flushList()
    paragraph.push(line.trim())
  }
  if (code) blocks.push({ kind: 'code', text: code.join('\n') })
  flush()
  return blocks
}

/** Inline **bold** and `code` only — anything else stays literal text. */
function inline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{part.slice(1, -1)}</code>
    return <Fragment key={i}>{part}</Fragment>
  })
}

function Markdown({ text }: { text: string }) {
  // The page header already names the document; drop the template's duplicate H1.
  const blocks = parseMarkdown(text)
  const start = blocks[0]?.kind === 'heading' && /^data processing agreement$/i.test(blocks[0].text) ? 1 : 0
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {blocks.slice(start).map((b, i) => {
        if (b.kind === 'heading') {
          const cls = b.level === 2 ? 'mt-6 text-lg font-semibold first:mt-0' : b.level === 3 ? 'mt-5 font-semibold first:mt-0' : 'mt-4 font-medium first:mt-0'
          return b.level === 2
            ? <h2 key={i} className={cls}>{inline(b.text)}</h2>
            : b.level === 3 ? <h3 key={i} className={cls}>{inline(b.text)}</h3> : <h4 key={i} className={cls}>{inline(b.text)}</h4>
        }
        if (b.kind === 'list') {
          const Tag = b.ordered ? 'ol' : 'ul'
          return (
            <Tag key={i} className={`${b.ordered ? 'list-decimal' : 'list-disc'} space-y-1 pl-5`}>
              {b.items.map((item, j) => <li key={j}>{inline(item)}</li>)}
            </Tag>
          )
        }
        if (b.kind === 'quote') return <blockquote key={i} className="border-l-2 pl-3 text-muted-foreground">{inline(b.text)}</blockquote>
        if (b.kind === 'code') return <pre key={i} className="overflow-x-auto rounded-md border bg-muted p-3 font-mono text-xs">{b.text}</pre>
        return <p key={i}>{inline(b.text)}</p>
      })}
    </div>
  )
}

const REGION_LABEL: Record<string, string> = { th: 'Thailand', sg: 'Singapore', us: 'United States' }
const regionName = (id: string) => REGION_LABEL[id.toLowerCase()] ?? id

export default function Dpa() {
  const { ws = '' } = useParams()
  const [params] = useSearchParams()
  const project = params.get('project') ?? undefined
  const q = useQuery({ queryKey: ['dpa', ws, project], queryFn: () => api.dpa(ws, project), enabled: !!ws })

  return (
    <div className="anim-page max-w-4xl">
      <PageHeader
        title="Data Processing Agreement"
        desc="The template that governs personal data processed in this workspace."
        actions={
          <>
            {q.data && <Badge className="hidden bg-card/70 text-foreground sm:inline-flex">v{q.data.version}</Badge>}
            {q.data && <Badge className="hidden bg-card/70 text-foreground md:inline-flex">{regionName(q.data.region)}</Badge>}
            <Button variant="outline" className="print:hidden" onClick={() => window.print()} disabled={!q.data}>
              <Printer className="h-4 w-4" aria-hidden />Print / Save as PDF
            </Button>
          </>
        }
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <Link to={`/${ws}/settings/privacy`} className="text-primary underline underline-offset-2">Privacy settings</Link>
          {q.data && (
            <span className="text-xs text-muted-foreground">
              Updated {typeof q.data.updated === 'number' ? fmtDate(q.data.updated) : q.data.updated} · {q.data.workspace}
            </span>
          )}
        </div>

        {q.isLoading ? (
          <Card className="space-y-3 p-6" role="status" aria-label="Loading the DPA">
            <div className="skeleton h-5 w-1/3" />
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-11/12" />
            <div className="skeleton h-4 w-4/5" />
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-2/3" />
          </Card>
        ) : q.isError ? (
          <Card className="flex flex-col items-center gap-2 p-8 text-center">
            <p role="alert" className="text-sm text-destructive">{q.error instanceof Error ? q.error.message : 'Could not load the DPA template.'}</p>
            <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
          </Card>
        ) : q.data ? (
          <Card className="p-6 sm:p-8">
            <div className="mb-4 flex items-start gap-2 border-b pb-4">
              <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
              <p className="text-xs text-muted-foreground">
                Version {q.data.version} · {regionName(q.data.region)}. This template is generated for your workspace; review it with legal counsel before signing.
              </p>
            </div>
            {q.data.markdown.trim() ? <Markdown text={q.data.markdown} /> : <p className="text-sm text-muted-foreground">The template is empty.</p>}
          </Card>
        ) : (
          <Card className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Spinner /> Loading…</Card>
        )}
      </div>
    </div>
  )
}
