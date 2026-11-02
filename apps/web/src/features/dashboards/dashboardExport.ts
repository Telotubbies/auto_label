import * as echarts from 'echarts/core'
import type { EChartsOption } from 'echarts'
import { classColor, viridis } from '@/lib/theme'
import { chartBase, toRgb, type ChartTheme } from '@/features/insights/charts'
import { buildWidgetOption, widgetCsv, type WidgetData, type WidgetSpec } from './widgetModel'

const WIDTH = 1200
const PAD = 28
const CHART_H = 300
const HEADER_H = 64
const BLOCK_GAP = 22

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('chart image could not be rendered'))
    image.src = src
  })
}

function drawTable(ctx: CanvasRenderingContext2D, spec: WidgetSpec, data: WidgetData, x: number, y: number, width: number, theme: ChartTheme) {
  const rows = widgetCsv(spec, data)
  const head = rows[0]
  const body = rows.slice(1, 9)
  const colWidth = width / head.length
  ctx.font = `600 12px ${theme.font}`
  ctx.fillStyle = theme.muted
  head.forEach((cell, i) => ctx.fillText(String(cell), x + i * colWidth, y + 14, colWidth - 12))
  ctx.font = `12px ${theme.font}`
  ctx.fillStyle = theme.fg
  body.forEach((row, r) => {
    row.forEach((cell, i) => ctx.fillText(String(cell), x + i * colWidth, y + 38 + r * 20, colWidth - 12))
  })
  if (rows.length - 1 > body.length) {
    ctx.fillStyle = theme.muted
    ctx.fillText(`+ ${rows.length - 1 - body.length} more rows in the CSV export`, x, y + 46 + body.length * 20)
  }
}

/** Compose the whole dashboard into one PNG: title block, then every widget in display order. */
export async function exportDashboardPng(name: string, items: { spec: WidgetSpec; data?: WidgetData }[], theme: ChartTheme, classOrder: string[] = []): Promise<void> {
  const drawable = items.filter((item): item is { spec: WidgetSpec; data: WidgetData } => !!item.data)
  if (!drawable.length) throw new Error('nothing to export yet')

  const heights = drawable.map(({ spec }) => {
    if (spec.chart === 'kpi') return 112
    if (spec.chart === 'table') return 220
    return CHART_H
  })
  const height = HEADER_H + heights.reduce((n, h) => n + h + 44 + BLOCK_GAP, 0)
  const canvas = document.createElement('canvas')
  canvas.width = WIDTH
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas is unavailable')

  ctx.fillStyle = theme.card
  ctx.fillRect(0, 0, WIDTH, height)
  ctx.fillStyle = theme.fg
  ctx.font = `700 24px ${theme.font}`
  ctx.fillText(name || 'Dashboard', PAD, 38)
  ctx.fillStyle = theme.muted
  ctx.font = `12px ${theme.font}`
  ctx.fillText(`LabelDesk · ${drawable.length} widgets · ${new Date().toLocaleString()}`, PAD, 58)

  const chartWidth = WIDTH - PAD * 2
  let y = HEADER_H
  for (const [index, { spec, data }] of drawable.entries()) {
    ctx.fillStyle = theme.fg
    ctx.font = `600 15px ${theme.font}`
    ctx.fillText(spec.title, PAD, y + 18)
    const top = y + 30
    if (spec.chart === 'kpi') {
      ctx.font = `700 36px ${theme.font}`
      ctx.fillText(`${data.total.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${data.unit}`, PAD, top + 44)
    } else if (spec.chart === 'table') {
      drawTable(ctx, spec, data, PAD, top, chartWidth, theme)
    } else {
      const host = document.createElement('div')
      host.style.cssText = `position:fixed;left:-10000px;top:0;width:${chartWidth}px;height:${CHART_H}px`
      document.body.appendChild(host)
      const chart = echarts.init(host, undefined, { renderer: 'canvas', width: chartWidth, height: CHART_H })
      try {
        const heat = Array.from({ length: 10 }, (_, i) => toRgb(viridis(i / 9)))
        const option = buildWidgetOption(spec, data, theme, (i) => toRgb(classColor(i)), heat, classOrder) as EChartsOption
        chart.setOption({ ...chartBase(theme, option), animation: false })
        const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: theme.card })
        const image = await loadImage(url)
        ctx.drawImage(image, PAD, top, chartWidth, CHART_H)
      } finally {
        chart.dispose()
        host.remove()
      }
    }
    y = top + heights[index] + BLOCK_GAP
  }

  const link = document.createElement('a')
  link.href = canvas.toDataURL('image/png')
  link.download = `${(name || 'dashboard').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'dashboard'}.png`
  document.body.appendChild(link)
  link.click()
  link.remove()
}
