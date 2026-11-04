import { useQuery } from '@tanstack/react-query'
import { ImageIcon } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { PlaygroundSample } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * Up to six recent annotated images of this workspace. Picking one only loads it as the image;
 * the Run button stays the only way to spend inference.
 */
export function SampleStrip({ ws, selectedId, onPick }: {
  ws: string
  selectedId: string | null
  onPick: (sample: PlaygroundSample) => void
}) {
  const samples = useQuery({
    queryKey: ['playground-samples', ws],
    queryFn: () => api.playgroundSamples(ws, 6),
    staleTime: 60_000,
  })

  return (
    <div>
      <div className="mb-1.5 text-sm font-medium">Sample images</div>
      {samples.isLoading ? (
        <div className="grid grid-cols-3 gap-2" aria-hidden="true">
          {Array.from({ length: 3 }, (_, i) => <div key={i} className="aspect-square animate-pulse rounded-md bg-muted" />)}
        </div>
      ) : samples.isError ? (
        <p className="text-xs text-muted-foreground">Could not load samples. Upload an image above.</p>
      ) : samples.data?.samples.length ? (
        <ul className="grid grid-cols-3 gap-2">
          {samples.data.samples.map((s) => (
            <li key={s.id}>
              <button type="button" aria-pressed={selectedId === s.id}
                aria-label={`Use sample ${s.name} from ${s.project.name}`} title={`${s.project.name} · ${s.name}`}
                onClick={() => onPick(s)}
                className={cn('block aspect-square w-full overflow-hidden rounded-md border bg-muted transition-shadow hover:border-ring',
                  selectedId === s.id && 'ring-2 ring-ring ring-offset-1')}>
                <img src={fileUrl(s.thumbnail)} alt="" loading="lazy" className="h-full w-full object-cover" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" />
          No annotated images in this workspace yet. Upload one above to try it.
        </p>
      )}
    </div>
  )
}
