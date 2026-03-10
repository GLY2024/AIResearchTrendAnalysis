<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { AnalysisRun } from '@/types'
import { analysisApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'
import ChartContainer from '@/components/common/ChartContainer.vue'
import StreamingText from '@/components/chat/StreamingText.vue'
import SkeletonCard from '@/components/common/SkeletonCard.vue'

const sessionStore = useSessionStore()
const backendState = useBackendState()
const runs = ref<AnalysisRun[]>([])
const loading = ref(false)
const running = ref<string | null>(null)
const actionError = ref('')

const analysisTypes = [
  { key: 'bibliometrics', label: 'Bibliometrics', description: 'H-index, citations, top authors, journals', icon: '📈' },
  { key: 'trend', label: 'Trend Analysis', description: 'Publication & citation trends over time', icon: '📊' },
  { key: 'network', label: 'Keyword Network', description: 'Keyword co-occurrence network', icon: '🔗' },
  { key: 'coauthor', label: 'Co-authorship', description: 'Author collaboration network', icon: '👥' },
  { key: 'topic_modeling', label: 'Topic Modeling', description: 'Discover research themes', icon: '🧠' },
] as const

async function loadRuns() {
  if (!sessionStore.currentSession) return
  loading.value = true
  actionError.value = ''
  try {
    runs.value = await analysisApi.list(sessionStore.currentSession.id)
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load analyses.'
    await checkBackend(true)
  } finally {
    loading.value = false
  }
}

async function runAnalysis(type: string) {
  if (!sessionStore.currentSession) return
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('analysis')
    return
  }
  running.value = type
  try {
    const result = await analysisApi.create({
      session_id: sessionStore.currentSession.id,
      analysis_type: type,
    })
    runs.value.unshift(result)
    pollForCompletion(result.id)
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to start analysis.'
    await checkBackend(true)
  } finally {
    running.value = null
  }
}

async function pollForCompletion(runId: number) {
  const maxAttempts = 60
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 5000))
    try {
      const updated = await analysisApi.get(runId)
      const idx = runs.value.findIndex(r => r.id === runId)
      if (idx !== -1) runs.value[idx] = updated
      if (updated.status === 'completed' || updated.status === 'failed') break
    } catch { break }
  }
}

function getLatestRun(type: string) {
  return runs.value.find(r => r.analysis_type === type)
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
      <div
        v-if="actionError"
        class="mb-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <!-- Analysis type cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div
          v-for="t in analysisTypes"
          :key="t.key"
          class="glass-card p-4 flex flex-col"
        >
          <div class="flex items-start gap-3 mb-3">
            <span class="text-2xl leading-none">{{ t.icon }}</span>
            <div class="flex-1 min-w-0">
              <h3 class="text-sm font-semibold text-[var(--text-primary)]">{{ t.label }}</h3>
              <p class="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">{{ t.description }}</p>
            </div>
          </div>
          <!-- Latest run status -->
          <div v-if="getLatestRun(t.key)" class="mb-3">
            <span :class="['badge text-[10px]', statusBadge[getLatestRun(t.key)!.status]]">
              {{ getLatestRun(t.key)!.status }}
            </span>
            <span class="text-[10px] text-[var(--text-muted)] ml-2">
              {{ new Date(getLatestRun(t.key)!.created_at).toLocaleString() }}
            </span>
          </div>
          <div class="mt-auto">
            <button
              class="glass-btn glass-btn-primary text-xs w-full"
              :disabled="running !== null || backendState.status !== 'online'"
              @click="runAnalysis(t.key)"
            >
              <span v-if="running === t.key" class="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin mr-1.5" />
              {{ running === t.key ? 'Running...' : 'Run' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <SkeletonCard v-for="i in 2" :key="i" height="300px" :lines="5" />
      </div>

      <!-- Results -->
      <div v-else class="space-y-6">
        <div v-if="runs.length === 0" class="text-[var(--text-muted)]">
          No analyses yet. Select a type above to run one.
        </div>

        <GlassCard v-for="run in runs" :key="run.id">
          <div class="flex items-center justify-between mb-4">
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

          <!-- Running indicator -->
          <div v-if="run.status === 'running' || run.status === 'pending'" class="streaming-bar w-full mb-4" />

          <!-- Charts -->
          <div
            v-if="run.chart_configs && run.chart_configs.length"
            class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-4"
          >
            <ChartContainer
              v-for="chart in run.chart_configs"
              :key="chart.id"
              :option="chart.option"
              :title="chart.title"
              :height="(['network', 'coauthor'].includes(run.analysis_type)) ? '500px' : '400px'"
            />
          </div>

          <!-- AI Interpretation with markdown -->
          <div v-if="run.ai_interpretation" class="mt-4 glass-card p-4">
            <h4 class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">AI Interpretation</h4>
            <div class="md-content">
              <StreamingText
                :text="run.ai_interpretation"
                :is-streaming="false"
              />
            </div>
          </div>
        </GlassCard>
      </div>
    </template>
  </div>
</template>
