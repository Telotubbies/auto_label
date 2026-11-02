/**
 * Viewport culling for the annotation canvas.
 *
 * The Stage is 1000 stage-units wide and `height` tall (the image aspect decides the height); one
 * annotation is one Konva node (or Group), so a 1,000-shape image mounts 1,000 nodes per paint.
 * These helpers live in stage pixels: the annotation's bounding box no longer depends on zoom, and
 * the viewport is the visible stage rectangle plus a screen-space margin. Pure and node-testable.
 */
export interface Bounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export interface ViewportInput {
  width: number
  height: number
  scale: number
  x: number
  y: number
}

/** Stage-units of margin around the visible rectangle, converted from screen pixels. */
export const CULL_MARGIN_PX = 96

interface ShapeLike {
  kind: string
  x?: number
  y?: number
  w?: number
  h?: number
  cx?: number
  cy?: number
  angle?: number
  points?: number[]
}

interface AnnotationLike {
  id: string
  shape: ShapeLike
}

/** Pixel-space corners, matching `imaging.obb_corners` in the API (clockwise at angle 0). */
export function obbCorners(s: { cx: number; cy: number; w: number; h: number; angle: number }, H: number, W = 1000) {
  const cx = s.cx * W, cy = s.cy * H, hw = (s.w * W) / 2, hh = (s.h * H) / 2
  const c = Math.cos(s.angle), sn = Math.sin(s.angle)
  return [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]].flatMap(([dx, dy]) => [cx + dx * c - dy * sn, cy + dx * sn + dy * c])
}

/**
 * Stage-pixel bounds of one annotation, or null for image-label annotations (`kind: 'class'`),
 * which are never canvas nodes.
 */
export function shapeBounds(shape: ShapeLike, W: number, H: number): Bounds | null {
  if (shape.kind === 'bbox') {
    const x = (shape.x ?? 0) * W, y = (shape.y ?? 0) * H
    return { minX: x, minY: y, maxX: x + (shape.w ?? 0) * W, maxY: y + (shape.h ?? 0) * H }
  }
  if (shape.kind === 'polygon') {
    const pts = shape.points ?? []
    if (pts.length < 2) return null
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (let i = 0; i < pts.length; i += 2) {
      const x = pts[i] * W, y = pts[i + 1] * H
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
    }
    return { minX, minY, maxX, maxY }
  }
  if (shape.kind === 'obb') {
    const corners = obbCorners({
      cx: shape.cx ?? 0, cy: shape.cy ?? 0, w: shape.w ?? 0, h: shape.h ?? 0, angle: shape.angle ?? 0,
    }, H, W)
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (let i = 0; i < corners.length; i += 2) {
      const x = corners[i], y = corners[i + 1]
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
    }
    return { minX, minY, maxX, maxY }
  }
  if (shape.kind === 'keypoints') {
    const pts = shape.points ?? []
    if (pts.length < 3) return null
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (let i = 0; i + 1 < pts.length; i += 3) {
      const x = pts[i] * W, y = pts[i + 1] * H
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
    }
    return { minX, minY, maxX, maxY }
  }
  return null
}

/** The visible stage rectangle for the current pan/zoom, inflated by `marginPx` screen pixels. */
export function viewportBounds(view: ViewportInput, marginPx = CULL_MARGIN_PX): Bounds {
  const scale = view.scale > 0 ? view.scale : 1
  const pad = marginPx / scale
  return {
    minX: -view.x / scale - pad,
    minY: -view.y / scale - pad,
    maxX: (view.width - view.x) / scale + pad,
    maxY: (view.height - view.y) / scale + pad,
  }
}

export function intersects(a: Bounds, b: Bounds) {
  return a.minX <= b.maxX && a.maxX >= b.minX && a.minY <= b.maxY && a.maxY >= b.minY
}

/**
 * Annotations whose bounding box intersects the viewport. `always` keeps the selected annotation
 * mounted so the Transformer always has its node, even after a pan moves it off screen.
 */
export function cullAnnotations<T extends AnnotationLike>(
  anns: T[], viewport: Bounds, opts: { width: number; height: number; always?: string | null },
): T[] {
  const always = opts.always ?? null
  const out: T[] = []
  for (const a of anns) {
    const bounds = shapeBounds(a.shape, opts.width, opts.height)
    if (!bounds) continue                      // image labels draw nothing
    if (a.id === always || intersects(bounds, viewport)) out.push(a)
  }
  return out
}
