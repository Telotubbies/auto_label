import type { Annotation, OcrData, OcrKind } from './types'

/** One class per OCR kind, named the same way the API's template endpoint creates them. */
export const OCR_CLASS: Record<OcrKind, string> = {
  text: 'text-line',
  keyvalue: 'key-value',
  table: 'table',
}

const blankCells = (rows: number, cols: number) =>
  Array.from({ length: rows }, () => Array.from({ length: cols }, () => ''))

export function emptyOcr(kind: OcrKind): OcrData {
  if (kind === 'text') return { kind, text: '' }
  if (kind === 'keyvalue') return { kind, key: '', value: '' }
  return { kind, rows: 2, cols: 3, cells: blankCells(2, 3) }
}

/** Resize a table's cells without losing what is already typed. */
export function resizeCells(cells: string[][] | undefined, rows: number, cols: number): string[][] {
  return Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) => cells?.[r]?.[c] ?? ''),
  )
}

/** The text a kind switch should carry over: a line, a value, or a table's first cell. */
function sourceText(ocr: OcrData): string {
  if (ocr.kind === 'text') return ocr.text ?? ''
  if (ocr.kind === 'keyvalue') return ocr.value ?? ocr.key ?? ''
  return ocr.cells?.[0]?.[0] ?? ''
}

/** Convert a payload to another kind, carrying over whatever text it held. */
export function convertOcr(ocr: OcrData, kind: OcrKind): OcrData {
  if (ocr.kind === kind) return ocr
  const text = sourceText(ocr)
  if (kind === 'text') return { kind, text }
  if (kind === 'keyvalue') return { kind, key: '', value: text }
  const rows = ocr.kind === 'table' ? ocr.rows ?? 2 : 2
  const cols = ocr.kind === 'table' ? ocr.cols ?? 3 : 3
  const cells = resizeCells(ocr.kind === 'table' ? ocr.cells : undefined, rows, cols)
  cells[0][0] = text
  return { kind, rows, cols, cells }
}

/** One-line label for an OCR annotation: the text, `key: value`, or the table size. */
export function ocrText(ann: Annotation): string {
  const ocr = ann.ocr
  if (!ocr) return ''
  if (ocr.kind === 'text') return ocr.text ?? ''
  if (ocr.kind === 'keyvalue') {
    const key = ocr.key?.trim() ?? ''
    return key ? `${key}: ${ocr.value ?? ''}` : ocr.value ?? ''
  }
  return `${ocr.rows ?? ocr.cells?.length ?? 0}×${ocr.cols ?? ocr.cells?.[0]?.length ?? 0} table`
}

// Same patterns and ordering as apps/backend/app/services/ocr.py, so the panel, canvas and
// exports hide exactly the same characters. Python's `\d`/`\w` are Unicode-aware, so the
// equivalents here are `\p{Nd}` / `[\p{L}\p{N}_]` with the `u` flag: Thai numerals and
// Thai-script emails are masked on both sides. Thai ID first (dashed or spaced), then plain digits.
const PII_PATTERNS: RegExp[] = [
  /(?<!\p{Nd})\p{Nd}[-\u00a0 ]\p{Nd}{4}[-\u00a0 ]\p{Nd}{5}[-\u00a0 ]\p{Nd}{2}[-\u00a0 ]\p{Nd}(?!\p{Nd})/gu,
  /(?<!\p{Nd})\p{Nd}{13}(?!\p{Nd})/gu,
  /(?<!\p{Nd})0[1-9](?:[-\s]?\p{Nd}){8}(?!\p{Nd})/gu,
  /[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+\.[\p{L}\p{N}_.-]+/gu,
]

/** Replace detected personal data with `*` of the same length, keeping the layout readable. */
export function maskPii(text: string): string {
  return PII_PATTERNS.reduce((out, pattern) => out.replace(pattern, (m) => '*'.repeat(m.length)), text)
}
