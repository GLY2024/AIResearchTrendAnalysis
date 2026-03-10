<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { SearchPlan, SearchPlanData } from '@/types'
import { searchApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { useWebSocket } from '@/composables/useWebSocket'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'
import CollapsibleInfoCard from '@/components/common/CollapsibleInfoCard.vue'

const router = useRouter()
const sessionStore = useSessionStore()
const backendState = useBackendState()

const plans = ref<SearchPlan[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)
const actionError = ref('')
const needsApiKey = ref(false)
const editingPlanId = ref<number | null>(null)
const draftPlanData = ref<SearchPlanData | null>(null)

const sourceOptions = ['openalex', 'scopus', 'arxiv']

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

let ws: ReturnType<typeof useWebSocket> | null = null

const sourceColors: Record<string, string> = {
  semantic_scholar: 'bg-blue-500/20 text-blue-300',
  openalex: 'bg-emerald-500/20 text-emerald-300',
  scopus: 'bg-orange-500/20 text-orange-300',
  pubmed: 'bg-rose-500/20 text-rose-300',
  crossref: 'bg-cyan-500/20 text-cyan-300',
}

const statusBadge: Record<string, string> = {
  draft: 'badge-warning',
  approved: 'badge-success',
  executing: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
  rejected: 'badge-error',
}

const draftCount = computed(() => plans.value.filter((plan) => plan.status === 'draft').length)
const runningCount = computed(() => plans.value.filter((plan) => plan.status === 'executing').length + activeProgress.value.size)
const completedCount = computed(() => plans.value.filter((plan) => plan.status === 'completed').length)
const totalQueries = computed(() =>
  plans.value.reduce((sum, plan) => sum + (plan.plan_data.queries?.length ?? 0), 0),
)

function getSourceClass(source: string): string {
  return sourceColors[source.toLowerCase()] || 'bg-white/10 text-[var(--text-secondary)]'
}

function getProgressPercent(planId: number): number {
  const progress = activeProgress.value.get(planId)
  if (!progress) return 0
  return Math.round(((progress.query_index + (progress.status === 'completed' ? 1 : 0.5)) / progress.total_queries) * 100)
}

function yearRangeLabel(plan: SearchPlan) {
  const from = plan.plan_data.year_range?.from
  const to = plan.plan_data.year_range?.to
  if (!from && !to) return 'Open range'
  return `${from ?? '...'} - ${to ?? 'present'}`
}

function setupWebSocket() {
  if (ws) ws.disconnect()
  if (!sessionStore.currentSession) return

  ws = useWebSocket(sessionStore.currentSession.id)

  ws.on('search_progress', (data: Record<string, unknown>) => {
    const progress = data as unknown as SearchProgress
    activeProgress.value.set(progress.plan_id, progress)
    const plan = plans.value.find((item) => item.id === progress.plan_id)
    if (plan && plan.status === 'approved') {
      plan.status = 'executing'
    }
  })

  ws.on('search_complete', (data: Record<string, unknown>) => {
    const planId = data.plan_id as number
    completedSearches.value.set(planId, { total_papers: data.total_papers as number })
    activeProgress.value.delete(planId)
    const plan = plans.value.find((item) => item.id === planId)
    if (plan) plan.status = 'completed'
  })

  ws.on('search_plan_approved', (data: Record<string, unknown>) => {
    const plan = plans.value.find((item) => item.id === (data.plan_id as number))
    if (plan) plan.status = 'approved'
  })

  ws.on('error', (data: Record<string, unknown>) => {
    if (data.error_code === 'no_api_key') {
      needsApiKey.value = true
      actionError.value = (data.message as string) || 'API key not configured.'
      return
    }
    const planId = data.plan_id as number | undefined
    if (!planId) return
    activeProgress.value.delete(planId)
    const plan = plans.value.find((item) => item.id === planId)
    if (plan) plan.status = 'failed'
  })
}

async function loadPlans() {
  if (!sessionStore.currentSession) return

  loading.value = true
  actionError.value = ''
  try {
    plans.value = await searchApi.listPlans(sessionStore.currentSession.id)
    const draftPlan = plans.value.find((plan) => plan.status === 'draft')
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
    const index = plans.value.findIndex((plan) => plan.id === planId)
    if (index !== -1) plans.value[index] = updated
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to update the search plan.'
    await checkBackend(true)
  }
}

function clonePlanData(plan: SearchPlan): SearchPlanData {
  const copied = JSON.parse(JSON.stringify(plan.plan_data)) as SearchPlanData
  copied.queries = copied.queries ?? []
  copied.inclusion_criteria = copied.inclusion_criteria ?? []
  copied.exclusion_criteria = copied.exclusion_criteria ?? []
  copied.year_range = copied.year_range ?? { from: null, to: null }
  copied.snowball_config = {
    enabled: copied.snowball_config?.enabled ?? false,
    approval_required: copied.snowball_config?.approval_required ?? true,
    approval_mode: copied.snowball_config?.approval_mode ?? 'batch',
    decision_mode: copied.snowball_config?.decision_mode ?? 'manual_review',
    max_hops: copied.snowball_config?.max_hops ?? 1,
    directions: copied.snowball_config?.directions ?? ['forward'],
    min_citation_threshold: copied.snowball_config?.min_citation_threshold ?? 10,
    max_seed_papers: copied.snowball_config?.max_seed_papers ?? 5,
    per_seed_limit: copied.snowball_config?.per_seed_limit ?? 25,
    max_candidates: copied.snowball_config?.max_candidates ?? 150,
    verification_mode: copied.snowball_config?.verification_mode ?? 'stable_identifier',
    ai_filter: {
      enabled: copied.snowball_config?.ai_filter?.enabled ?? true,
      min_score: copied.snowball_config?.ai_filter?.min_score ?? 0.55,
      auto_import_score: copied.snowball_config?.ai_filter?.auto_import_score ?? 0.8,
    },
  }
  return copied
}

function startEditing(plan: SearchPlan) {
  editingPlanId.value = plan.id
  expandedId.value = plan.id
  draftPlanData.value = clonePlanData(plan)
}

function cancelEditing() {
  editingPlanId.value = null
  draftPlanData.value = null
}

function addQuery() {
  if (!draftPlanData.value) return
  draftPlanData.value.queries.push({
    query: '',
    source: 'openalex',
    rationale: '',
  })
}

function removeQuery(index: number) {
  if (!draftPlanData.value) return
  draftPlanData.value.queries.splice(index, 1)
}

function setSnowballDirection(direction: 'forward' | 'backward', checked: boolean) {
  if (!draftPlanData.value) return
  const next = new Set(draftPlanData.value.snowball_config.directions ?? [])
  if (checked) next.add(direction)
  else next.delete(direction)
  draftPlanData.value.snowball_config.directions = [...next]
}

async function savePlanEdits(planId: number) {
  if (!draftPlanData.value) return
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('search plan editing')
    return
  }

  try {
    const updated = await searchApi.planAction(planId, 'modify', draftPlanData.value as unknown as Record<string, unknown>)
    const index = plans.value.findIndex((plan) => plan.id === planId)
    if (index !== -1) plans.value[index] = updated
    editingPlanId.value = null
    draftPlanData.value = null
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to save plan edits.'
    await checkBackend(true)
  }
}

function toggle(planId: number) {
  expandedId.value = expandedId.value === planId ? null : planId
}

watch(() => sessionStore.currentSessionId, loadPlans)
onMounted(loadPlans)
onUnmounted(() => {
  if (ws) ws.disconnect()
})
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Search design</div>
      <h2 class="page-hero__title">Review the plan before you spend time and API budget executing it.</h2>
      <p class="page-hero__copy">
        This page now foregrounds status, query volume, and execution progress, so the plan reads like an operational brief rather than raw JSON.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Drafts</span>
          <span class="stat-card__value">{{ draftCount }}</span>
          <span class="stat-card__hint">Plans waiting for a human decision</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Running</span>
          <span class="stat-card__value">{{ runningCount }}</span>
          <span class="stat-card__hint">Plans currently executing or streaming progress</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Completed</span>
          <span class="stat-card__value">{{ completedCount }}</span>
          <span class="stat-card__hint">Searches that already populated the library</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Total queries</span>
          <span class="stat-card__value">{{ totalQueries }}</span>
          <span class="stat-card__hint">Across every plan in the current session</span>
        </div>
      </div>
    </section>

    <CollapsibleInfoCard
      eyebrow="Review guide"
      title="How to evaluate a plan before execution"
    >
      <div class="grid gap-3 lg:grid-cols-3">
        <div class="callout">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Approve</div>
          <p class="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            Use approval when the topic, year range, and source mix are already acceptable and you want to start collecting papers immediately.
          </p>
        </div>
        <div class="callout">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Edit</div>
          <p class="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            Rejecting a plan no longer blocks the workflow. You can reopen it, adjust queries, snowball rules, and notes, then save the revised draft.
          </p>
        </div>
        <div class="callout">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Snowball</div>
          <p class="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            Treat snowball as a second-stage expansion. Keep it off unless the seed set is clean enough to justify proposal review and manual approval.
          </p>
        </div>
      </div>
    </CollapsibleInfoCard>

    <div v-if="!sessionStore.currentSession" class="surface-panel p-8">
      <h3 class="surface-panel__title">Select a session first.</h3>
      <p class="surface-panel__copy mt-3">Search plans are generated from the conversation inside a specific session.</p>
    </div>

    <template v-else>
      <div v-if="loading" class="surface-panel p-8 text-[var(--text-muted)]">
        Loading plans...
      </div>

      <div
        v-else-if="needsApiKey"
        class="callout callout--accent"
      >
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="text-sm font-semibold text-[var(--text-primary)]">API key required</div>
            <div class="mt-1 text-sm text-[var(--text-secondary)]">{{ actionError }}</div>
          </div>
          <button class="glass-btn glass-btn-primary" @click="router.push('/settings'); needsApiKey = false; actionError = ''">
            Go to settings
          </button>
        </div>
      </div>

      <div
        v-else-if="actionError"
        class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <div v-else-if="plans.length === 0" class="surface-panel p-8">
        <h3 class="surface-panel__title">No search plans yet.</h3>
        <p class="surface-panel__copy mt-3">
          Use the Chat workspace to refine the topic, then generate a search plan from there.
        </p>
      </div>

      <div v-else class="space-y-4">
        <GlassCard v-for="plan in plans" :key="plan.id">
          <template #header>
            <div class="surface-panel__header !mb-0 cursor-pointer" @click="toggle(plan.id)">
              <div class="min-w-0 flex-1">
                <p class="surface-panel__eyebrow">Plan topic</p>
                <div class="flex flex-wrap items-center gap-3">
                  <h3 class="surface-panel__title truncate">{{ plan.plan_data.topic }}</h3>
                  <span :class="['badge', statusBadge[plan.status]]">{{ plan.status }}</span>
                </div>
                <div class="mt-3 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                  <span class="capsule">{{ plan.plan_data.queries?.length ?? 0 }} queries</span>
                  <span class="capsule">{{ yearRangeLabel(plan) }}</span>
                  <span v-if="plan.plan_data.snowball_config?.enabled" class="capsule">Snowball enabled</span>
                </div>
              </div>

              <div class="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                <span>{{ new Date(plan.created_at).toLocaleDateString() }}</span>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  class="transition-transform"
                  :class="expandedId === plan.id ? 'rotate-180' : ''"
                >
                  <path d="M4 6l4 4 4-4" />
                </svg>
              </div>
            </div>
          </template>

          <div v-if="activeProgress.has(plan.id)" class="mb-5 space-y-3">
            <div class="flex flex-col gap-2 text-sm text-[var(--text-secondary)] lg:flex-row lg:items-center lg:justify-between">
              <span>
                Searching {{ activeProgress.get(plan.id)!.source }}:
                "{{ activeProgress.get(plan.id)!.query.substring(0, 72) }}"
              </span>
              <span>
                {{ activeProgress.get(plan.id)!.query_index + 1 }} / {{ activeProgress.get(plan.id)!.total_queries }}
              </span>
            </div>

            <div class="h-2 w-full overflow-hidden rounded-full bg-white/6">
              <div
                class="h-full rounded-full transition-all duration-500"
                style="background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))"
                :style="{ width: `${getProgressPercent(plan.id)}%` }"
              />
            </div>

            <div class="text-xs text-[var(--text-muted)]">
              {{ activeProgress.get(plan.id)!.total_found ?? 0 }} papers found so far
            </div>
          </div>

          <div v-if="completedSearches.has(plan.id)" class="mb-5 callout callout--success">
            Search complete: {{ completedSearches.get(plan.id)!.total_papers }} papers were added to the library.
          </div>

          <div v-if="expandedId === plan.id" class="space-y-5 text-sm">
            <template v-if="editingPlanId === plan.id && draftPlanData">
              <div class="grid gap-4 lg:grid-cols-2">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Topic</label>
                  <input v-model="draftPlanData.topic" class="glass-input text-sm" type="text" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Max results per query</label>
                  <input v-model.number="draftPlanData.max_results_per_query" class="glass-input text-sm" type="number" min="10" />
                </div>
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Description</label>
                <textarea v-model="draftPlanData.description" class="glass-input min-h-[120px] text-sm" />
              </div>

              <div class="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Year from</label>
                  <input v-model.number="draftPlanData.year_range.from" class="glass-input text-sm" type="number" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Year to</label>
                  <input v-model.number="draftPlanData.year_range.to" class="glass-input text-sm" type="number" />
                </div>
                <label class="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  <input v-model="draftPlanData.snowball_config.enabled" type="checkbox" class="accent-[var(--accent-primary)]" />
                  Enable snowball
                </label>
                <label class="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  <input v-model="draftPlanData.snowball_config.ai_filter!.enabled" type="checkbox" class="accent-[var(--accent-primary)]" />
                  AI screening
                </label>
              </div>

              <div v-if="draftPlanData.snowball_config.enabled" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Hops</label>
                  <input v-model.number="draftPlanData.snowball_config.max_hops" class="glass-input text-sm" type="number" min="1" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Min citations</label>
                  <input v-model.number="draftPlanData.snowball_config.min_citation_threshold" class="glass-input text-sm" type="number" min="0" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Seed papers</label>
                  <input v-model.number="draftPlanData.snowball_config.max_seed_papers" class="glass-input text-sm" type="number" min="1" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Per-seed limit</label>
                  <input v-model.number="draftPlanData.snowball_config.per_seed_limit" class="glass-input text-sm" type="number" min="5" />
                </div>
              </div>

              <div v-if="draftPlanData.snowball_config.enabled" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Max candidates</label>
                  <input v-model.number="draftPlanData.snowball_config.max_candidates" class="glass-input text-sm" type="number" min="10" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Verification</label>
                  <select v-model="draftPlanData.snowball_config.verification_mode" class="glass-input text-sm">
                    <option value="none">No verification</option>
                    <option value="stable_identifier">Stable identifier</option>
                    <option value="cross_source">Cross-source</option>
                  </select>
                </div>
                <div class="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Directions</div>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2">
                      <input
                        type="checkbox"
                        class="accent-[var(--accent-primary)]"
                        :checked="draftPlanData.snowball_config.directions.includes('forward')"
                        @change="setSnowballDirection('forward', ($event.target as HTMLInputElement).checked)"
                      />
                      Forward
                    </label>
                    <label class="flex items-center gap-2">
                      <input
                        type="checkbox"
                        class="accent-[var(--accent-primary)]"
                        :checked="draftPlanData.snowball_config.directions.includes('backward')"
                        @change="setSnowballDirection('backward', ($event.target as HTMLInputElement).checked)"
                      />
                      Backward
                    </label>
                  </div>
                </div>
              </div>

              <div>
                <div class="mb-3 flex items-center justify-between gap-3">
                  <h4 class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                    Queries ({{ draftPlanData.queries.length }})
                  </h4>
                  <button class="glass-btn" @click="addQuery">Add query</button>
                </div>

                <div class="space-y-3">
                  <div v-for="(query, index) in draftPlanData.queries" :key="index" class="callout space-y-3">
                    <div class="grid gap-3 lg:grid-cols-[160px_minmax(0,1fr)_100px]">
                      <select v-model="query.source" class="glass-input text-sm">
                        <option v-for="source in sourceOptions" :key="source" :value="source">{{ source }}</option>
                      </select>
                      <input v-model="query.query" class="glass-input text-sm font-mono" type="text" placeholder="Search query" />
                      <button class="glass-btn" @click="removeQuery(index)">Remove</button>
                    </div>
                    <textarea v-model="query.rationale" class="glass-input min-h-[92px] text-sm" placeholder="Why this query matters" />
                  </div>
                </div>
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Notes</label>
                <textarea v-model="draftPlanData.notes" class="glass-input min-h-[100px] text-sm" />
              </div>

              <div class="flex flex-wrap gap-3 pt-2">
                <button class="glass-btn glass-btn-primary" :disabled="backendState.status !== 'online'" @click.stop="savePlanEdits(plan.id)">
                  Save draft
                </button>
                <button class="glass-btn" @click.stop="cancelEditing">
                  Cancel
                </button>
              </div>
            </template>

            <template v-else>
              <p class="text-[var(--text-secondary)] leading-7">{{ plan.plan_data.description }}</p>

              <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <div class="callout">
                  <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Year range</div>
                  <div class="mt-1 text-sm text-[var(--text-primary)]">{{ yearRangeLabel(plan) }}</div>
                </div>
                <div class="callout" v-if="plan.plan_data.max_results_per_query">
                  <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Max per query</div>
                  <div class="mt-1 text-sm text-[var(--text-primary)]">{{ plan.plan_data.max_results_per_query }}</div>
                </div>
                <div class="callout" v-if="plan.plan_data.snowball_config?.enabled">
                  <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Snowball</div>
                  <div class="mt-1 text-sm text-[var(--text-primary)]">
                    {{ plan.plan_data.snowball_config.directions?.join(', ') ?? 'forward, backward' }}
                  </div>
                </div>
              </div>

              <div>
                <h4 class="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                  Queries ({{ plan.plan_data.queries?.length ?? 0 }})
                </h4>
                <div class="space-y-3">
                  <div
                    v-for="(query, index) in plan.plan_data.queries"
                    :key="index"
                    class="callout"
                  >
                    <div class="mb-2 flex items-center gap-2">
                      <span class="rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]" :class="getSourceClass(query.source)">
                        {{ query.source }}
                      </span>
                    </div>
                    <div class="font-mono text-xs leading-6 text-[var(--text-primary)]">{{ query.query }}</div>
                    <div class="mt-2 text-xs leading-6 text-[var(--text-muted)]">{{ query.rationale }}</div>
                  </div>
                </div>
              </div>

              <CollapsibleInfoCard
                v-if="plan.plan_data.inclusion_criteria?.length || plan.plan_data.exclusion_criteria?.length || plan.plan_data.notes"
                eyebrow="Screening notes"
                title="Criteria and planner notes"
              >
                <div class="space-y-4">
                  <div class="grid gap-4 lg:grid-cols-2" v-if="plan.plan_data.inclusion_criteria?.length || plan.plan_data.exclusion_criteria?.length">
                    <div v-if="plan.plan_data.inclusion_criteria?.length" class="callout callout--success">
                      <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Inclusion criteria</div>
                      <ul class="list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
                        <li v-for="(criterion, index) in plan.plan_data.inclusion_criteria" :key="index">{{ criterion }}</li>
                      </ul>
                    </div>

                    <div v-if="plan.plan_data.exclusion_criteria?.length" class="callout callout--warm">
                      <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Exclusion criteria</div>
                      <ul class="list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
                        <li v-for="(criterion, index) in plan.plan_data.exclusion_criteria" :key="index">{{ criterion }}</li>
                      </ul>
                    </div>
                  </div>

                  <div v-if="plan.plan_data.notes" class="callout">
                    <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Planner note</div>
                    <div class="text-sm italic text-[var(--text-secondary)]">
                      {{ plan.plan_data.notes }}
                    </div>
                  </div>
                </div>
              </CollapsibleInfoCard>

              <div v-if="['draft', 'rejected'].includes(plan.status)" class="flex flex-wrap gap-3 pt-2">
                <button
                  class="glass-btn"
                  :disabled="backendState.status !== 'online'"
                  @click.stop="startEditing(plan)"
                >
                  Edit plan
                </button>
                <button
                  class="glass-btn glass-btn-primary"
                  :disabled="backendState.status !== 'online'"
                  @click.stop="handleAction(plan.id, 'approve')"
                >
                  Approve and execute
                </button>
                <button
                  v-if="plan.status === 'draft'"
                  class="glass-btn"
                  :disabled="backendState.status !== 'online'"
                  @click.stop="handleAction(plan.id, 'reject')"
                >
                  Reject
                </button>
              </div>
            </template>
          </div>
        </GlassCard>
      </div>
    </template>
  </div>
</template>
