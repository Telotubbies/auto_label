// Where a chart would draw axes but has no series, say so in one sentence (T-523). The box keeps
// the height of the chart it replaces, so the card does not jump when data is missing.
export default function SeriesEmpty({ title, hint, height = 240 }: { title: string; hint?: string; height?: number }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-4 text-center" style={{ height }}>
      <p className="text-sm text-muted-foreground">{title}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
