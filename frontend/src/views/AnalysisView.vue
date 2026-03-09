<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { AnalysisRun } from '@/types'
import { analysisApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import GlassCard from '@/components/common/GlassCard.vue'

import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart, ScatterChart, GraphChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components'

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

const sessionStore = useSessionStore()
const runs = ref<AnalysisRun[]>([])
const loading = ref(false)
const running = ref<string | null>(null)

const analysisTypes = [
  { key: 'bibliometrics', label: 'Bibliometrics', description: 'Publication trends, top authors, journals' },
  { key: 'trend', label: 'Trend Analysis', description: 'Research topic trends over time' },
  { key: 'network', label: 'Network Analysis', description: 'Co-authorship and citation networks' },
] as const

async function loadRuns() {
  if (!sessionStore.currentSession) return
  loading.value = true
  try {
    runs.value = await analysisApi.list(sessionStore.currentSession.id)
  } finally {
    loading.value = false
  }
}

async function runAnalysis(type: string) {
  if (!sessionStore.currentSession) return
  running.value = type
  try {
    const result = await analysisApi.create({
      session_id: sessionStore.currentSession.id,
      analysis_type: type,
    })
    runs.value.unshift(result)
  } finally {
    running.value = null
  }
}

function chartTheme(option: Record<string, unknown>) {
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    ...option,
  }
}

const statusBadge: Record<string, string> = {
  pending: 'badge-warning',
  running: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
}

watch(() => sessionStore.currentSessionId, loadRuns)
onMounted(loadRuns)
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-[var(--text-primary)] mb-1">Analysis</h1>
    <p class="text-sm text-[var(--text-secondary)] mb-6">
      Run analyses on your collected papers.
    </p>

    <div v-if="!sessionStore.currentSession" class="text-[var(--text-muted)]">
      Select a session first.
    </div>

    <template v-else>
      <!-- Action buttons -->
      <div class="flex flex-wrap gap-3 mb-6">
        <button
          v-for="t in analysisTypes"
          :key="t.key"
          class="glass-btn glass-btn-primary"
          :disabled="running !== null"
          @click="runAnalysis(t.key)"
        >
          <span v-if="running === t.key" class="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin mr-2" />
          {{ t.label }}
        </button>
      </div>

      <div v-if="loading" class="text-[var(--text-muted)]">Loading analyses...</div>

      <!-- Results -->
      <div v-else class="space-y-6">
        <div v-if="runs.length === 0" class="text-[var(--text-muted)]">
          No analyses yet. Click a button above to run one.
        </div>

        <GlassCard v-for="run in runs" :key="run.id">
          <div class="flex items-center justify-between mb-3">
            <div>
              <span class="font-medium text-[var(--text-primary)] capitalize">
                {{ run.analysis_type.replace('_', ' ') }}
              </span>
              <span :class="['badge ml-3', statusBadge[run.status]]">
                {{ run.status }}
              </span>
            </div>
            <span class="text-xs text-[var(--text-muted)]">
              {{ new Date(run.created_at).toLocaleString() }}
            </span>
          </div>

          <!-- Charts -->
          <div
            v-if="run.chart_configs && run.chart_configs.length"
            class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4"
          >
            <div
              v-for="chart in run.chart_configs"
              :key="chart.id"
              class="glass-card p-4"
            >
              <h4 class="text-sm font-medium text-[var(--text-primary)] mb-2">{{ chart.title }}</h4>
              <VChart
                :option="chartTheme(chart.option)"
                class="w-full h-64"
                autoresize
              />
            </div>
          </div>

          <!-- AI Interpretation -->
          <div v-if="run.ai_interpretation" class="mt-3">
            <h4 class="text-xs text-[var(--text-muted)] mb-1">AI Interpretation</h4>
            <p class="text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed">
              {{ run.ai_interpretation }}
            </p>
          </div>
        </GlassCard>
      </div>
    </template>
  </div>
</template>
