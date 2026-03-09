<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { Report } from '@/types'
import { reportApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import GlassCard from '@/components/common/GlassCard.vue'

import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const sessionStore = useSessionStore()
const reports = ref<Report[]>([])
const selectedReport = ref<Report | null>(null)
const loading = ref(false)
const generating = ref(false)

async function loadReports() {
  if (!sessionStore.currentSession) return
  loading.value = true
  try {
    reports.value = await reportApi.list(sessionStore.currentSession.id)
    if (reports.value.length && !selectedReport.value) {
      selectedReport.value = reports.value[0]
    }
  } finally {
    loading.value = false
  }
}

async function generateReport() {
  if (!sessionStore.currentSession) return
  generating.value = true
  try {
    const report = await reportApi.generate({
      session_id: sessionStore.currentSession.id,
    })
    reports.value.unshift(report)
    selectedReport.value = report
  } finally {
    generating.value = false
  }
}

function selectReport(report: Report) {
  selectedReport.value = report
}

function chartTheme(option: Record<string, unknown>) {
  return { backgroundColor: 'transparent', textStyle: { color: '#94a3b8' }, ...option }
}

const statusBadge: Record<string, string> = {
  draft: 'badge-warning',
  generating: 'badge-info',
  completed: 'badge-success',
}

watch(() => sessionStore.currentSessionId, () => {
  selectedReport.value = null
  loadReports()
})
onMounted(loadReports)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-[var(--text-primary)]">Report</h1>
        <p class="text-sm text-[var(--text-secondary)]">
          Generate and view research reports.
        </p>
      </div>
      <button
        class="glass-btn glass-btn-primary"
        :disabled="generating || !sessionStore.currentSession"
        @click="generateReport"
      >
        <span v-if="generating" class="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin mr-2" />
        Generate Report
      </button>
    </div>

    <div v-if="!sessionStore.currentSession" class="text-[var(--text-muted)]">
      Select a session first.
    </div>

    <template v-else>
      <div v-if="loading" class="text-[var(--text-muted)]">Loading reports...</div>

      <div v-else-if="reports.length === 0" class="text-[var(--text-muted)]">
        No reports yet. Click "Generate Report" to create one.
      </div>

      <div v-else class="flex gap-6">
        <!-- Report list sidebar -->
        <div class="w-56 shrink-0 space-y-2">
          <div
            v-for="report in reports"
            :key="report.id"
            class="glass-card p-3 cursor-pointer"
            :class="selectedReport?.id === report.id ? 'border-[var(--accent-primary)]' : ''"
            @click="selectReport(report)"
          >
            <div class="text-sm font-medium text-[var(--text-primary)] truncate">
              {{ report.title || `Report v${report.version}` }}
            </div>
            <div class="flex items-center justify-between mt-1">
              <span :class="['badge text-[10px]', statusBadge[report.status]]">
                {{ report.status }}
              </span>
              <span class="text-[10px] text-[var(--text-muted)]">
                {{ new Date(report.created_at).toLocaleDateString() }}
              </span>
            </div>
          </div>
        </div>

        <!-- Report content -->
        <GlassCard v-if="selectedReport" class="flex-1 min-w-0">
          <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
            {{ selectedReport.title || `Report v${selectedReport.version}` }}
          </h2>

          <!-- Markdown content -->
          <div
            class="prose prose-invert prose-sm max-w-none text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed"
          >
            {{ selectedReport.content_markdown }}
          </div>

          <!-- Embedded charts -->
          <div
            v-for="(chartGroup, gi) in selectedReport.chart_configs"
            :key="gi"
            class="grid grid-cols-1 lg:grid-cols-2 gap-4 my-4"
          >
            <div v-for="chart in chartGroup" :key="chart.id" class="glass-card p-4">
              <h4 class="text-sm font-medium text-[var(--text-primary)] mb-2">{{ chart.title }}</h4>
              <VChart
                :option="chartTheme(chart.option)"
                class="w-full h-64"
                autoresize
              />
            </div>
          </div>
        </GlassCard>
      </div>
    </template>
  </div>
</template>
