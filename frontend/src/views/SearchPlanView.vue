<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { SearchPlan } from '@/types'
import { searchApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { useWebSocket } from '@/composables/useWebSocket'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'

const router = useRouter()
const sessionStore = useSessionStore()
const backendState = useBackendState()
const plans = ref<SearchPlan[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)
const actionError = ref('')
const needsApiKey = ref(false)

// Search progress tracking
interface SearchProgress {
  plan_id: number
  query_index: number
  total_queries: number
  source: string
  query: string
  status: string
  results_count?: number
  total_found?: number
}

const activeProgress = ref<Map<number, SearchProgress>>(new Map())
const completedSearches = ref<Map<number, { total_papers: number }>>(new Map())

// WebSocket connection
let ws: ReturnType<typeof useWebSocket> | null = null

function setupWebSocket() {
  if (ws) ws.disconnect()
  if (!sessionStore.currentSession) return

  ws = useWebSocket(sessionStore.currentSession.id)

  ws.on('search_progress', (data: Record<string, unknown>) => {
    const progress = data as unknown as SearchProgress
    activeProgress.value.set(progress.plan_id, progress)
    const plan = plans.value.find(p => p.id === progress.plan_id)
    if (plan && plan.status === 'approved') {
      plan.status = 'executing'
    }
  })

  ws.on('search_complete', (data: Record<string, unknown>) => {
    const planId = data.plan_id as number
    completedSearches.value.set(planId, { total_papers: data.total_papers as number })
    activeProgress.value.delete(planId)
    const plan = plans.value.find(p => p.id === planId)
    if (plan) {
      plan.status = 'completed'
    }
  })

  ws.on('search_plan_approved', (data: Record<string, unknown>) => {
    const plan = plans.value.find(p => p.id === (data.plan_id as number))
    if (plan) {
      plan.status = 'approved'
    }
  })

  ws.on('error', (data: Record<string, unknown>) => {
    if (data.error_code === 'no_api_key') {
      needsApiKey.value = true
      actionError.value = (data.message as string) || 'API key not configured.'
      return
    }
    const planId = data.plan_id as number | undefined
    if (planId) {
      activeProgress.value.delete(planId)
      const plan = plans.value.find(p => p.id === planId)
      if (plan) plan.status = 'failed'
    }
  })
}

async function loadPlans() {
  if (!sessionStore.currentSession) return
  loading.value = true
  actionError.value = ''
  try {
    plans.value = await searchApi.listPlans(sessionStore.currentSession.id)
    // Auto-expand draft plans
    const draftPlan = plans.value.find(p => p.status === 'draft')
    if (draftPlan) expandedId.value = draftPlan.id
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load search plans.'
    await checkBackend(true)
  } finally {
    loading.value = false
  }
  setupWebSocket()
}

async function handleAction(planId: number, action: 'approve' | 'reject') {
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('search plan approval')
    return
  }

  try {
    const updated = await searchApi.planAction(planId, action)
    const idx = plans.value.findIndex(p => p.id === planId)
    if (idx !== -1) plans.value[idx] = updated
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to update the search plan.'
    await checkBackend(true)
  }
}

function toggle(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

function getProgressPercent(planId: number): number {
  const p = activeProgress.value.get(planId)
  if (!p) return 0
  return Math.round(((p.query_index + (p.status === 'completed' ? 1 : 0.5)) / p.total_queries) * 100)
}

// Source color mapping
const sourceColors: Record<string, string> = {
  'semantic_scholar': 'bg-blue-500/20 text-blue-400',
  'openalex': 'bg-green-500/20 text-green-400',
  'scopus': 'bg-orange-500/20 text-orange-400',
  'pubmed': 'bg-red-500/20 text-red-400',
  'crossref': 'bg-purple-500/20 text-purple-400',
}
function getSourceClass(source: string): string {
  return sourceColors[source.toLowerCase()] || 'bg-white/10 text-[var(--text-secondary)]'
}

const statusBadge: Record<string, string> = {
  draft: 'badge-warning',
  approved: 'badge-success',
  executing: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
  rejected: 'badge-error',
}

watch(() => sessionStore.currentSessionId, loadPlans)
onMounted(loadPlans)
onUnmounted(() => {
  if (ws) ws.disconnect()
})
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-[var(--text-primary)] mb-1">Search Plans</h1>
    <p class="text-sm text-[var(--text-secondary)] mb-6">
      Review and approve search strategies generated by the AI.
    </p>

    <div v-if="!sessionStore.currentSession" class="text-[var(--text-muted)]">
      Select a session first.
    </div>

    <div v-else-if="loading" class="text-[var(--text-muted)]">Loading plans...</div>

    <!-- API key missing prompt -->
    <div
      v-if="needsApiKey"
      class="mb-4 rounded-xl border border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/10 px-5 py-4"
    >
      <p class="text-sm font-medium text-[var(--text-primary)] mb-2">API Key Required</p>
      <p class="text-sm text-[var(--text-secondary)] mb-3">{{ actionError }}</p>
      <button
        class="glass-btn glass-btn-primary text-sm"
        @click="router.push('/settings'); needsApiKey = false; actionError = ''"
      >
        Go to Settings
      </button>
    </div>
    <div
      v-else-if="actionError"
      class="mb-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]"
    >
      {{ actionError }}
    </div>

    <div v-else-if="plans.length === 0" class="text-[var(--text-muted)]">
      No search plans yet. Ask the AI to create one in Chat.
    </div>

    <div v-else class="space-y-4">
      <GlassCard v-for="plan in plans" :key="plan.id">
        <!-- Header row -->
        <div
          class="flex items-center justify-between cursor-pointer"
          @click="toggle(plan.id)"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium text-[var(--text-primary)]">
                {{ plan.plan_data.topic }}
              </span>
              <span :class="['badge', statusBadge[plan.status]]">
                {{ plan.status }}
              </span>
            </div>
            <!-- Plan summary -->
            <div class="flex items-center gap-3 mt-1.5 text-xs text-[var(--text-muted)]">
              <span>{{ plan.plan_data.queries?.length ?? 0 }} queries</span>
              <span v-if="plan.plan_data.year_range?.from || plan.plan_data.year_range?.to">
                {{ plan.plan_data.year_range?.from ?? '...' }}–{{ plan.plan_data.year_range?.to ?? 'now' }}
              </span>
              <span v-if="plan.plan_data.snowball_config?.enabled" class="badge badge-info text-[10px]">
                snowball
              </span>
            </div>
          </div>
          <div class="flex items-center gap-3 shrink-0">
            <span class="text-[var(--text-muted)] text-xs">
              {{ new Date(plan.created_at).toLocaleDateString() }}
            </span>
            <svg
              width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
              class="text-[var(--text-muted)] transition-transform" :class="expandedId === plan.id ? 'rotate-180' : ''"
            >
              <path d="M4 6l4 4 4-4" />
            </svg>
          </div>
        </div>

        <!-- Search progress bar -->
        <div
          v-if="activeProgress.has(plan.id)"
          class="mt-3 space-y-2"
        >
          <div class="flex items-center justify-between text-xs text-[var(--text-secondary)]">
            <span>
              Searching: {{ activeProgress.get(plan.id)!.source }} -
              "{{ activeProgress.get(plan.id)!.query.substring(0, 50) }}"
            </span>
            <span>
              {{ activeProgress.get(plan.id)!.query_index + 1 }} / {{ activeProgress.get(plan.id)!.total_queries }}
            </span>
          </div>
          <div class="w-full h-2 rounded-full bg-white/5 overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500"
              style="background: var(--accent-primary)"
              :style="{ width: getProgressPercent(plan.id) + '%' }"
            />
          </div>
          <div class="text-xs text-[var(--text-muted)]">
            {{ activeProgress.get(plan.id)!.total_found ?? 0 }} papers found so far
          </div>
        </div>

        <!-- Completed search summary -->
        <div
          v-if="completedSearches.has(plan.id)"
          class="mt-3 text-sm text-[var(--accent-secondary)]"
        >
          Search complete: {{ completedSearches.get(plan.id)!.total_papers }} papers found
        </div>

        <!-- Expanded detail -->
        <div v-if="expandedId === plan.id" class="mt-5 space-y-4 text-sm">
          <p class="text-[var(--text-secondary)]">{{ plan.plan_data.description }}</p>

          <!-- Year range & max results -->
          <div class="flex flex-wrap gap-4 text-xs">
            <div v-if="plan.plan_data.year_range?.from || plan.plan_data.year_range?.to">
              <span class="text-[var(--text-muted)]">Year range:</span>
              {{ plan.plan_data.year_range.from ?? '...' }} - {{ plan.plan_data.year_range.to ?? 'present' }}
            </div>
            <div v-if="plan.plan_data.max_results_per_query">
              <span class="text-[var(--text-muted)]">Max results per query:</span>
              {{ plan.plan_data.max_results_per_query }}
            </div>
          </div>

          <!-- Snowball config -->
          <div v-if="plan.plan_data.snowball_config?.enabled" class="text-xs text-[var(--text-muted)]">
            Snowball: {{ plan.plan_data.snowball_config.directions?.join(', ') ?? 'forward, backward' }}
            ({{ plan.plan_data.snowball_config.max_hops ?? 2 }} hops, min citations: {{ plan.plan_data.snowball_config.min_citation_threshold ?? 5 }})
          </div>

          <!-- Queries -->
          <div>
            <h4 class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
              Queries ({{ plan.plan_data.queries?.length ?? 0 }})
            </h4>
            <div class="space-y-2.5">
              <div
                v-for="(q, i) in plan.plan_data.queries"
                :key="i"
                class="glass-card p-4"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span
                    class="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
                    :class="getSourceClass(q.source)"
                  >
                    {{ q.source }}
                  </span>
                </div>
                <div class="text-[var(--text-primary)] font-mono text-xs leading-relaxed">{{ q.query }}</div>
                <div class="text-[var(--text-muted)] text-xs mt-1.5">{{ q.rationale }}</div>
              </div>
            </div>
          </div>

          <!-- Inclusion / Exclusion as bullet lists -->
          <div v-if="plan.plan_data.inclusion_criteria?.length" class="space-y-1">
            <h4 class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Inclusion Criteria</h4>
            <ul class="list-disc list-inside text-sm text-[var(--text-secondary)] space-y-0.5 pl-1">
              <li v-for="(c, i) in plan.plan_data.inclusion_criteria" :key="i">{{ c }}</li>
            </ul>
          </div>
          <div v-if="plan.plan_data.exclusion_criteria?.length" class="space-y-1">
            <h4 class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Exclusion Criteria</h4>
            <ul class="list-disc list-inside text-sm text-[var(--text-secondary)] space-y-0.5 pl-1">
              <li v-for="(c, i) in plan.plan_data.exclusion_criteria" :key="i">{{ c }}</li>
            </ul>
          </div>

          <!-- Notes -->
          <div v-if="plan.plan_data.notes" class="text-[var(--text-muted)] text-xs italic">
            {{ plan.plan_data.notes }}
          </div>

          <!-- Actions -->
          <div v-if="plan.status === 'draft'" class="flex gap-3 pt-2">
            <button
              class="glass-btn glass-btn-primary"
              :disabled="backendState.status !== 'online'"
              @click.stop="handleAction(plan.id, 'approve')"
            >
              Approve & Execute
            </button>
            <button
              class="glass-btn"
              :disabled="backendState.status !== 'online'"
              @click.stop="handleAction(plan.id, 'reject')"
            >
              Reject
            </button>
          </div>
        </div>
      </GlassCard>
    </div>
  </div>
</template>
