/** Text equivalent for the lineage edges.
 *
 * The DAG draws its connections in an aria-hidden SVG, so screen-reader and keyboard users get the
 * same relationships from these rows: one per edge, with both node labels resolved and the edge kind
 * spelled out. Pure and DOM-free so the rules run in Node's test runner.
 */
import type { LineageEdge, LineageNode } from '@/lib/types'

export interface EdgeRow {
  source: string
  target: string
  kind: string
}

const EDGE_LABEL: Record<LineageEdge['kind'], string> = {
  images: 'Images',
  training: 'Training',
  deployment: 'Deployment',
}

/** Edges whose endpoints are both in `nodes`; a filtered-out or deleted node takes its edges with it,
 * matching what the graph draws. */
export function edgeRows(nodes: LineageNode[], edges: LineageEdge[]): EdgeRow[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const rows: EdgeRow[] = []
  for (const edge of edges) {
    const source = byId.get(edge.source)
    const target = byId.get(edge.target)
    if (!source || !target) continue
    rows.push({ source: source.label, target: target.label, kind: EDGE_LABEL[edge.kind] })
  }
  return rows
}

/** The selected node's incoming and outgoing connections, for the detail panel. */
export function nodeConnections(
  nodes: LineageNode[],
  edges: LineageEdge[],
  id: string,
): { incoming: EdgeRow[]; outgoing: EdgeRow[] } {
  return {
    incoming: edgeRows(nodes, edges.filter((edge) => edge.target === id)),
    outgoing: edgeRows(nodes, edges.filter((edge) => edge.source === id)),
  }
}
