import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  BarChart,
  GraphChart,
  LineChart,
  PieChart,
  ScatterChart,
} from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'

let registered = false

export function registerECharts() {
  if (registered) return

  use([
    CanvasRenderer,
    BarChart,
    LineChart,
    PieChart,
    ScatterChart,
    GraphChart,
    TitleComponent,
    TooltipComponent,
    LegendComponent,
    GridComponent,
    DataZoomComponent,
  ])

  registered = true
}

function themeAxis(axis: unknown) {
  if (!axis || typeof axis !== 'object') return axis

  const typedAxis = axis as Record<string, unknown>
  return {
    ...typedAxis,
    axisLine: {
      ...(typedAxis.axisLine as Record<string, unknown> | undefined),
      lineStyle: {
        color: 'rgba(191, 208, 231, 0.28)',
        ...((typedAxis.axisLine as Record<string, unknown> | undefined)?.lineStyle as Record<string, unknown> | undefined),
      },
    },
    axisLabel: {
      color: '#a8bad3',
      ...((typedAxis.axisLabel as Record<string, unknown> | undefined) ?? {}),
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(191, 208, 231, 0.08)',
        ...((typedAxis.splitLine as Record<string, unknown> | undefined)?.lineStyle as Record<string, unknown> | undefined),
      },
      ...((typedAxis.splitLine as Record<string, unknown> | undefined) ?? {}),
    },
  }
}

function themeAxisCollection(axis: unknown) {
  if (Array.isArray(axis)) return axis.map(themeAxis)
  return themeAxis(axis)
}

export function chartTheme(option: Record<string, unknown>): Record<string, unknown> {
  const colors = ['#4db8ff', '#ff9e57', '#95df78', '#ffe27a', '#7acbff', '#ff7d7d']

  return {
    color: colors,
    backgroundColor: 'transparent',
    textStyle: {
      color: '#bfd0e7',
      fontFamily: '"Aptos", "Segoe UI Variable Display", "Segoe UI", sans-serif',
    },
    grid: {
      left: 24,
      right: 18,
      top: 56,
      bottom: 24,
      containLabel: true,
      ...(option.grid as Record<string, unknown> | undefined),
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(7, 17, 31, 0.94)',
      borderColor: 'rgba(171, 202, 239, 0.18)',
      textStyle: { color: '#f6fbff' },
      ...((option.tooltip as Record<string, unknown> | undefined) ?? {}),
    },
    legend: {
      textStyle: { color: '#8ea5c2' },
      ...((option.legend as Record<string, unknown> | undefined) ?? {}),
    },
    xAxis: themeAxisCollection(option.xAxis),
    yAxis: themeAxisCollection(option.yAxis),
    ...option,
  }
}
