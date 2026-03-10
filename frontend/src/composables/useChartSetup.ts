import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  GraphChart,
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
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

export function chartTheme(option: Record<string, unknown>): Record<string, unknown> {
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    ...option,
  }
}
