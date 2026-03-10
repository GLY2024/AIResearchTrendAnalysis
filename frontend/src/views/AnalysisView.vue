<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { AnalysisRun } from '@/types'
import { analysisApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'
import CollapsibleInfoCard from '@/components/common/CollapsibleInfoCard.vue'
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
  {
    key: 'bibliometrics',
    label: 'Bibliometrics',
    description: 'Track publication volume, citations, venues, and author influence.',
    icon: 'M4 18h16M7 14v4M12 9v9M17 5v13',
    tone: 'text-[var(--accent-primary)]',
  },
  {
    key: 'trend',
    label: 'Trend analysis',
    description: 'Reveal temporal momentum and citation acceleration.',
    icon: 'M4 15l4-4 3 3 5-7 3 3',
    tone: 'text-[var(--accent-secondary)]',
  },
  {
    key: 'network',
    label: 'Keyword network',
    description: 'Map co-occurrence structure and cluster formation.',
    icon: 'M5 6a2 2 0 1 0 0.001 0zM18 9a2 2 0 1 0 0.001 0zM9 18a2 2 0 1 0 0.001 0zM6.7 7.1l9.6 1.8M8.1 16.4l8.3-5.8M6.6 7.8l2.2 8.4',
    tone: 'text-[var(--accent-tertiary)]',
  },
  {
    key: 'coauthor',
    label: 'Co-authorship',
    description: 'Expose collaboration patterns among authors and labs.',
    icon: 'M7 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM17 13a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM3.5 19a4.5 4.5 0 0 1 9 0M13 19a4 4 0 0 1 8 0',
    tone: 'text-[var(--info)]',
  },
  {
    key: 'topic_modeling',
    label: 'Topic modeling',
    description: 'Surface latent themes and semantic neighborhoods.',
    icon: 'M5 6h14M5 12h14M5 18h8M17 18l2-2m0 0-2-2m2 2h-5',
    tone: 'text-[var(--warning)]',
  },
] as const

const statusBadge: Record<string, string> = {
  pending: 'badge-warning',
  running: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
}

const completedRuns = computed(() => runs.value.filter((run) => run.status === 'completed').length)
const failedRuns = computed(() => runs.value.filter((run) => run.status === 'failed').length)
const activeRuns = computed(() => runs.value.filter((run) => run.status === 'running' || run.status === 'pending').length)
const latestRunLabel = computed(() => {
  const firstRun = runs.value[0]
  if (!firstRun) return 'No analyses yet'
  return new Date(firstRun.created_at).toLocaleString()
})

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
    void pollForCompletion(result.id)
  } catch (err) {
    const detail = (err as { response?: { status?: number; data?: { detail?: unknown } } })?.response?.data?.detail
    if ((err as { response?: { status?: number } })?.response?.status === 409 && detail && typeof detail === 'object') {
      const message = (detail as { message?: string; existing_status?: string }).message
      const existingStatus = (detail as { existing_status?: string }).existing_status
      actionError.value = existingStatus ? `${message} Existing run status: ${existingStatus}.` : (message ?? 'This analysis has already been run for the current paper selection.')
    } else {
      actionError.value = err instanceof Error ? err.message : 'Failed to start analysis.'
    }
    await checkBackend(true)
  } finally {
    running.value = null
  }
}

async function pollForCompletion(runId: number) {
  const maxAttempts = 60
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5000))
    try {
      const updated = await analysisApi.get(runId)
      const index = runs.value.findIndex((run) => run.id === runId)
      if (index !== -1) runs.value[index] = updated
      if (updated.status === 'completed' || updated.status === 'failed') break
    } catch {
      break
    }
  }
}

function getLatestRun(type: string) {
  return runs.value.find((run) => run.analysis_type === type)
}

watch(() => sessionStore.currentSessionId, loadRuns)
onMounted(loadRuns)
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Insight engine</div>
      <h2 class="page-hero__title">Transform the library into charts that can survive a supervisor review.</h2>
      <p class="page-hero__copy">
        This stage is now structured around a left control rail and a right evidence column, so the run launcher and the outputs
        no longer compete visually.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Completed</span>
          <span class="stat-card__value">{{ completedRuns }}</span>
          <span class="stat-card__hint">Finished runs ready for interpretation</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">In progress</span>
          <span class="stat-card__value">{{ activeRuns }}</span>
          <span class="stat-card__hint">Pending or actively generating</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Failed</span>
          <span class="stat-card__value">{{ failedRuns }}</span>
          <span class="stat-card__hint">Runs needing a rerun or debugging</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Latest update</span>
          <span class="stat-card__value text-[1rem] !leading-6">{{ latestRunLabel }}</span>
          <span class="stat-card__hint">Most recent analysis timestamp</span>
        </div>
      </div>
    </section>

    <div v-if="!sessionStore.currentSession" class="surface-panel p-8">
      <h3 class="surface-panel__title">Select a session first.</h3>
      <p class="surface-panel__copy mt-3">
        Analysis is attached to a session because it depends on the collected paper corpus.
      </p>
    </div>

    <template v-else>
      <div
        v-if="actionError"
        class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <div class="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div class="space-y-4">
          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Run launcher</p>
                  <h3 class="surface-panel__title">Choose the next lens</h3>
                  <p class="surface-panel__copy">
                    Each analysis type now reads like a report-building action rather than a generic button.
                  </p>
                </div>
              </div>
            </template>

            <div class="space-y-3">
              <button
                v-for="analysis in analysisTypes"
                :key="analysis.key"
                class="glass-card glass-card--interactive w-full p-4 text-left"
                :disabled="running !== null || backendState.status !== 'online'"
                @click="runAnalysis(analysis.key)"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/[0.05]" :class="analysis.tone">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                      <path :d="analysis.icon" />
                    </svg>
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="text-sm font-semibold text-[var(--text-primary)]">{{ analysis.label }}</span>
                      <span
                        v-if="getLatestRun(analysis.key)"
                        :class="['badge', statusBadge[getLatestRun(analysis.key)!.status]]"
                      >
                        {{ getLatestRun(analysis.key)!.status }}
                      </span>
                    </div>
                    <p class="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{{ analysis.description }}</p>
                    <p v-if="getLatestRun(analysis.key)" class="mt-2 text-xs text-[var(--text-muted)]">
                      Last run: {{ new Date(getLatestRun(analysis.key)!.created_at).toLocaleString() }}
                    </p>
                  </div>
                </div>

                <div class="mt-4 flex items-center justify-between">
                  <span class="text-xs text-[var(--text-muted)]">
                    {{ running === analysis.key ? 'Run queued...' : 'Start this analysis' }}
                  </span>
                  <span v-if="running === analysis.key" class="inline-block h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                </div>
              </button>
            </div>
          </GlassCard>

          <CollapsibleInfoCard eyebrow="Storyline" title="Recommended presentation order">
            <div class="space-y-3">
              <div class="callout callout--accent">
                <div class="text-sm font-semibold text-[var(--text-primary)]">1. Start with trend and bibliometrics</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Lead with scale, growth, venues, and high-impact authors so the audience understands the field shape.
                </div>
              </div>
              <div class="callout">
                <div class="text-sm font-semibold text-[var(--text-primary)]">2. Move into structure</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Network and topic modeling should explain how themes cluster rather than just listing keywords.
                </div>
              </div>
            </div>
          </CollapsibleInfoCard>
        </div>

        <div class="space-y-6">
          <div v-if="loading" class="space-y-4">
            <SkeletonCard v-for="index in 3" :key="index" height="280px" :lines="5" />
          </div>

          <div
            v-else-if="runs.length === 0"
            class="surface-panel p-8"
          >
            <div class="surface-panel__header">
              <div>
                <p class="surface-panel__eyebrow">No output yet</p>
                <h3 class="surface-panel__title">Run the first analysis to populate the evidence column.</h3>
              </div>
            </div>
            <p class="surface-panel__copy">
              The right side will show chart panels and model-written interpretation once a run starts producing results.
            </p>
          </div>

          <GlassCard v-for="run in runs" :key="run.id">
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Run output</p>
                  <div class="flex flex-wrap items-center gap-3">
                    <h3 class="surface-panel__title capitalize">
                      {{ run.analysis_type.replace('_', ' ') }}
                    </h3>
                    <span :class="['badge', statusBadge[run.status]]">{{ run.status }}</span>
                  </div>
                </div>
                <div class="text-xs text-[var(--text-muted)]">
                  {{ new Date(run.created_at).toLocaleString() }}
                </div>
              </div>
            </template>

            <div v-if="run.status === 'running' || run.status === 'pending'" class="mb-4">
              <div class="streaming-bar w-full" />
            </div>

            <div
              v-if="run.chart_configs && run.chart_configs.length"
              class="grid grid-cols-1 gap-5 xl:grid-cols-2"
            >
              <ChartContainer
                v-for="chart in run.chart_configs"
                :key="chart.id"
                :option="chart.option"
                :title="chart.title"
                :height="(['network', 'coauthor'].includes(run.analysis_type)) ? '500px' : '400px'"
              />
            </div>

            <div v-if="run.ai_interpretation" class="mt-5 rounded-[22px] border border-white/8 bg-white/[0.03] p-5">
              <h4 class="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">AI interpretation</h4>
              <div class="md-content">
                <StreamingText
                  :text="run.ai_interpretation"
                  :is-streaming="false"
                />
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </template>
  </div>
</template>
