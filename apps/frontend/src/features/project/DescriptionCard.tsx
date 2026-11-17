import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { api, patch } from '@/lib/api'
import type { Project } from '@/lib/types'
import { Button, Card, toast } from '@/components/ui'
import { copy } from '@/features/settings/SettingsChrome'

const MAX = 600

/** T-023: the blurb visitors read, saved where the author writes it, beside the public address. */
export function DescriptionCard({ ws, project, loading = false }: { ws: string; project: Project; loading?: boolean }) {
  const qc = useQueryClient()
  const [text, setText] = useState(project.description)
  const [saving, setSaving] = useState(false)
  const [failed, setFailed] = useState(false)
  const dirty = text !== project.description

  const save = () => {
    const value = text.trim()
    setSaving(true)
    setFailed(false)
    patch(api.P(ws, project.slug), { description: value })
      .then(() => {
        setText(value)
        qc.invalidateQueries({ queryKey: ['project', ws, project.slug] })
        qc.invalidateQueries({ queryKey: ['projects', ws] })
        toast.ok('Saved')
      })
      .catch(() => setFailed(true))
      .finally(() => setSaving(false))
  }

  return (
    <Card className="space-y-4 p-5">
      <div>
        <h2 className="font-semibold">Description</h2>
        <p className="text-sm text-muted-foreground">Visitors and teammates read this first.</p>
      </div>
      {loading ? (
        <div className="space-y-2" aria-hidden>
          <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
        </div>
      ) : (
        <>
          <label className="block">
            <span className="sr-only">Description</span>
            <textarea rows={6} maxLength={MAX} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="What is this dataset for, and what is in it?"
              className="w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring placeholder:text-muted-foreground" />
            <span className="mt-1 block text-right text-xs text-muted-foreground tabular-nums">{text.length}/{MAX}</span>
          </label>
          {failed && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              Could not save — your text is kept.
              <Button variant="outline" size="sm" onClick={save}>Retry</Button>
            </div>
          )}
          <div className="flex justify-end"><Button onClick={save} disabled={!dirty || saving}>Save description</Button></div>
          <div className="flex items-center gap-2 border-t pt-3 text-sm">
            <span className="shrink-0 font-medium">Public link</span>
            {project.visibility === 'public' ? (
              <>
                <code className="truncate text-xs text-muted-foreground">{project.publicPath}</code>
                <button className="cursor-pointer rounded p-1 text-muted-foreground hover:text-foreground"
                  onClick={() => copy(project.publicPath ?? '', 'Public link copied')} aria-label="Copy public link">
                  <Copy className="h-4 w-4" />
                </button>
              </>
            ) : (
              <span className="text-muted-foreground">Private. Make it public from the project menu.</span>
            )}
          </div>
        </>
      )}
    </Card>
  )
}
