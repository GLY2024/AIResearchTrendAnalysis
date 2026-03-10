<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Paper } from '@/types'
import { paperApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import SkeletonCard from '@/components/common/SkeletonCard.vue'
import CollapsibleInfoCard from '@/components/common/CollapsibleInfoCard.vue'

const sessionStore = useSessionStore()
const backendState = useBackendState()

const papers = ref<Paper[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)
const selectedIds = ref<Set<number>>(new Set())
const actionError = ref('')
const showFilters = ref(true)
const totalPapers = ref(0)
const filteredTotal = ref(0)
const includedTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref<10 | 20 | 50>(20)

const filterSource = ref('')
const filterDiscovery = ref('')
const filterYearFrom = ref<number | null>(null)
const filterYearTo = ref<number | null>(null)
const filterIncludedOnly = ref(false)
const searchQuery = ref('')
const sortKey = ref<'title' | 'year' | 'citation_count'>('citation_count')
const sortAsc = ref(false)

const availableSources = ref<string[]>([])
const availableMethods = ref<string[]>([])
const pageSizeOptions: Array<10 | 20 | 50> = [10, 20, 50]

const hasActiveFilters = computed(() =>
  Boolean(filterSource.value || filterDiscovery.value || filterYearFrom.value || filterYearTo.value || filterIncludedOnly.value),
)

const includedCount = computed(() => includedTotal.value)
const selectedCount = computed(() => selectedIds.value.size)
const sourceCount = computed(() => availableSources.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredTotal.value / pageSize.value)))
const pageStart = computed(() => (filteredTotal.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1))
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, filteredTotal.value))

function clearFilters() {
  filterSource.value = ''
  filterDiscovery.value = ''
  filterYearFrom.value = null
  filterYearTo.value = null
  filterIncludedOnly.value = false
}

function buildListParams() {
  return {
    included_only: filterIncludedOnly.value || undefined,
    year_from: filterYearFrom.value || undefined,
    year_to: filterYearTo.value || undefined,
    source: filterSource.value || undefined,
    discovery_method: filterDiscovery.value || undefined,
    search: searchQuery.value.trim() || undefined,
    sort_by: sortKey.value,
    sort_asc: sortAsc.value,
    limit: pageSize.value,
    offset: (currentPage.value - 1) * pageSize.value,
  }
}

function buildCountParams() {
  return {
    included_only: filterIncludedOnly.value || undefined,
    year_from: filterYearFrom.value || undefined,
    year_to: filterYearTo.value || undefined,
    source: filterSource.value || undefined,
    discovery_method: filterDiscovery.value || undefined,
    search: searchQuery.value.trim() || undefined,
  }
}

function paperAuthors(paper: Paper) {
  return Array.isArray(paper.authors) ? paper.authors : []
}

function paperKeywords(paper: Paper) {
  return Array.isArray(paper.keywords) ? paper.keywords : []
}

function paperFields(paper: Paper) {
  return Array.isArray(paper.fields) ? paper.fields : []
}

async function loadPapers() {
  if (!sessionStore.currentSession) return

  loading.value = true
  actionError.value = ''
  try {
    const params = buildListParams()
    const countParams = buildCountParams()
    const [page, filteredCount, total, included, response] = await Promise.all([
      paperApi.list(sessionStore.currentSession.id, params),
      paperApi.count(sessionStore.currentSession.id, countParams),
      paperApi.count(sessionStore.currentSession.id),
      paperApi.count(sessionStore.currentSession.id, { included_only: true }),
      paperApi.sources(sessionStore.currentSession.id),
    ])

    papers.value = Array.isArray(page.items) ? page.items : []
    filteredTotal.value = filteredCount.count
    totalPapers.value = total.count
    includedTotal.value = included.count
    availableSources.value = response.sources
    availableMethods.value = response.discovery_methods.filter((method) => !method.includes('snowball'))

    if (currentPage.value > pageCount.value) {
      currentPage.value = pageCount.value
      return
    }

    selectedIds.value = new Set(
      [...selectedIds.value].filter((id) => papers.value.some((paper) => paper.id === id)),
    )
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load papers.'
    await checkBackend(true)
  } finally {
    loading.value = false
  }
}

function sortMarker(key: typeof sortKey.value) {
  if (sortKey.value !== key) return ''
  return sortAsc.value ? 'asc' : 'desc'
}

function toggleSort(key: typeof sortKey.value) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
    return
  }

  sortKey.value = key
  sortAsc.value = false
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function selectAll() {
  if (selectedIds.value.size === papers.value.length) {
    selectedIds.value = new Set()
    return
  }

  selectedIds.value = new Set(papers.value.map((paper) => paper.id))
}

async function batchInclude(include: boolean) {
  if (selectedIds.value.size === 0) return

  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('paper updates')
    return
  }

  try {
    await paperApi.batchUpdate([...selectedIds.value], include)
    selectedIds.value = new Set()
    await loadPapers()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to update selected papers.'
    await checkBackend(true)
  }
}

async function batchDelete() {
  if (selectedIds.value.size === 0) return
  if (!confirm(`Delete ${selectedIds.value.size} papers?`)) return

  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('paper deletion')
    return
  }

  try {
    await paperApi.batchDelete([...selectedIds.value])
    selectedIds.value = new Set()
    await loadPapers()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to delete selected papers.'
    await checkBackend(true)
  }
}

function goToPreviousPage() {
  if (currentPage.value > 1) currentPage.value -= 1
}

function goToNextPage() {
  if (currentPage.value < pageCount.value) currentPage.value += 1
}

watch(() => sessionStore.currentSessionId, () => {
  currentPage.value = 1
  expandedId.value = null
  selectedIds.value = new Set()
  void loadPapers()
})

watch(
  [
    filterSource,
    filterDiscovery,
    filterYearFrom,
    filterYearTo,
    filterIncludedOnly,
    searchQuery,
    sortKey,
    sortAsc,
    pageSize,
  ],
  () => {
    expandedId.value = null
    selectedIds.value = new Set()
    if (currentPage.value !== 1) {
      currentPage.value = 1
      return
    }
    void loadPapers()
  },
)

watch(currentPage, () => {
  expandedId.value = null
  selectedIds.value = new Set()
  void loadPapers()
})

onMounted(loadPapers)
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Corpus management</div>
      <h2 class="page-hero__title">Inspect, filter, and curate the paper library before analysis.</h2>
      <p class="page-hero__copy">
        The library now reads as a curation workspace, with the corpus counts and selection state visible before you touch the table.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Total papers</span>
          <span class="stat-card__value">{{ totalPapers }}</span>
          <span class="stat-card__hint">All records attached to the session</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Included set</span>
          <span class="stat-card__value">{{ includedCount }}</span>
          <span class="stat-card__hint">Current keep list for downstream analysis</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Visible now</span>
          <span class="stat-card__value">{{ filteredTotal }}</span>
          <span class="stat-card__hint">After filters and text search</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Sources</span>
          <span class="stat-card__value">{{ sourceCount }}</span>
          <span class="stat-card__hint">Distinct acquisition channels represented</span>
        </div>
      </div>
    </section>

    <div v-if="!sessionStore.currentSession" class="surface-panel p-8">
      <h3 class="surface-panel__title">Select a session first.</h3>
      <p class="surface-panel__copy mt-3">The paper library is tied to the session-level search workflow.</p>
    </div>

    <template v-else>
      <div
        v-if="actionError"
        class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div class="space-y-4">
          <div class="surface-panel p-4">
            <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <input
                v-model="searchQuery"
                type="text"
                class="glass-input"
                placeholder="Search by title, abstract, journal, or author..."
              />

              <div class="flex flex-wrap gap-2">
                <span class="capsule">Selected {{ selectedCount }}</span>
                <span class="capsule">Included {{ includedCount }}</span>
              </div>
            </div>
          </div>

          <div class="glass-card overflow-hidden">
            <button
              class="flex w-full items-center justify-between px-4 py-4 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
              @click="showFilters = !showFilters"
            >
              <div>
                <div class="text-left font-semibold text-[var(--text-primary)]">Filters</div>
                <div class="mt-1 text-xs text-[var(--text-muted)]">
                  Source, discovery method, publication year, and inclusion state.
                </div>
              </div>

              <div class="flex items-center gap-3">
                <button
                  v-if="hasActiveFilters"
                  class="text-xs font-semibold text-[var(--accent-primary)] hover:underline"
                  @click.stop="clearFilters"
                >
                  Clear all
                </button>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  class="transition-transform"
                  :class="showFilters ? 'rotate-180' : ''"
                >
                  <path d="M4 6l4 4 4-4" />
                </svg>
              </div>
            </button>

            <div v-if="showFilters" class="grid gap-4 border-t border-white/8 px-4 pb-4 pt-4 md:grid-cols-2 xl:grid-cols-5">
              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Source</label>
                <select v-model="filterSource" class="glass-input text-sm">
                  <option value="">All</option>
                  <option v-for="source in availableSources" :key="source" :value="source">{{ source }}</option>
                </select>
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Found via</label>
                <select v-model="filterDiscovery" class="glass-input text-sm">
                  <option value="">All</option>
                  <option v-for="method in availableMethods" :key="method" :value="method">{{ method }}</option>
                </select>
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Year from</label>
                <input v-model.number="filterYearFrom" type="number" class="glass-input text-sm" placeholder="2020" />
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Year to</label>
                <input v-model.number="filterYearTo" type="number" class="glass-input text-sm" placeholder="2026" />
              </div>

              <label class="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-[var(--text-secondary)]">
                <input v-model="filterIncludedOnly" type="checkbox" class="accent-[var(--accent-primary)]" />
                Included only
              </label>
            </div>
          </div>

          <div v-if="selectedIds.size > 0" class="flex flex-wrap gap-2">
            <button class="glass-btn" :disabled="backendState.status !== 'online'" @click="batchInclude(true)">Include selected</button>
            <button class="glass-btn" :disabled="backendState.status !== 'online'" @click="batchInclude(false)">Exclude selected</button>
            <button class="glass-btn text-[var(--error)]" :disabled="backendState.status !== 'online'" @click="batchDelete">Delete selected</button>
          </div>

          <div v-if="loading" class="space-y-2">
            <SkeletonCard v-for="index in 6" :key="index" height="64px" :lines="1" />
          </div>

          <div v-else class="glass-card overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full min-w-[980px] text-sm">
                <thead class="bg-white/[0.03]">
                  <tr class="border-b border-white/8 text-left text-[var(--text-muted)]">
                    <th class="w-10 p-3">
                      <input
                        type="checkbox"
                        class="accent-[var(--accent-primary)]"
                        :checked="papers.length > 0 && selectedIds.size > 0 && selectedIds.size === papers.length"
                        @change="selectAll"
                      />
                    </th>
                    <th class="cursor-pointer p-3 hover:text-[var(--text-primary)]" @click="toggleSort('title')">
                      Title <span class="text-[10px] uppercase">{{ sortMarker('title') }}</span>
                    </th>
                    <th class="p-3">Authors</th>
                    <th class="w-24 cursor-pointer p-3 hover:text-[var(--text-primary)]" @click="toggleSort('year')">
                      Year <span class="text-[10px] uppercase">{{ sortMarker('year') }}</span>
                    </th>
                    <th class="w-24 cursor-pointer p-3 hover:text-[var(--text-primary)]" @click="toggleSort('citation_count')">
                      Cites <span class="text-[10px] uppercase">{{ sortMarker('citation_count') }}</span>
                    </th>
                    <th class="w-28 p-3">Source</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="paper in papers" :key="paper.id">
                    <tr
                      class="cursor-pointer border-b border-white/5 transition-colors hover:bg-white/[0.04]"
                      :class="{ 'bg-[var(--accent-primary)]/8': selectedIds.has(paper.id) }"
                    >
                      <td class="p-3" @click.stop>
                        <input
                          type="checkbox"
                          class="accent-[var(--accent-primary)]"
                          :checked="selectedIds.has(paper.id)"
                          @change="toggleSelect(paper.id)"
                        />
                      </td>
                      <td class="p-3 text-[var(--text-primary)]" @click="expandedId = expandedId === paper.id ? null : paper.id">
                        <span v-if="paper.is_included" class="mr-2 inline-block h-2 w-2 rounded-full bg-[var(--success)]" />
                        <span v-else class="mr-2 inline-block h-2 w-2 rounded-full bg-white/20" />
                        {{ paper.title }}
                      </td>
                      <td class="max-w-[260px] truncate p-3 text-[var(--text-secondary)]" @click="expandedId = expandedId === paper.id ? null : paper.id">
                        {{ paperAuthors(paper).slice(0, 3).map((author) => author.name).join(', ') }}
                        {{ paperAuthors(paper).length > 3 ? ` +${paperAuthors(paper).length - 3}` : '' }}
                      </td>
                      <td class="p-3 text-[var(--text-secondary)]">{{ paper.year ?? '-' }}</td>
                      <td class="p-3 text-[var(--text-secondary)]">{{ paper.citation_count }}</td>
                      <td class="p-3 text-[var(--text-muted)]">{{ paper.source ?? '-' }}</td>
                    </tr>

                    <tr v-if="expandedId === paper.id">
                      <td colspan="6" class="border-b border-white/5 bg-white/[0.03] p-5">
                        <div class="space-y-5">
                          <div>
                            <h5 class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Abstract</h5>
                            <p class="text-sm leading-7 text-[var(--text-secondary)]">
                              {{ paper.abstract || 'No abstract available.' }}
                            </p>
                          </div>

                          <div v-if="paperKeywords(paper).length">
                            <h5 class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Keywords</h5>
                            <div class="flex flex-wrap gap-2">
                              <span v-for="keyword in paperKeywords(paper)" :key="keyword" class="badge badge-info">{{ keyword }}</span>
                            </div>
                          </div>

                          <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                            <div v-if="paper.journal" class="callout">
                              <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Journal</div>
                              <div class="mt-1 text-sm text-[var(--text-primary)]">{{ paper.journal }}</div>
                            </div>
                            <div v-if="paper.discovery_method" class="callout">
                              <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Found via</div>
                              <div class="mt-1 text-sm text-[var(--text-primary)]">{{ paper.discovery_method }}</div>
                            </div>
                            <div v-if="paperFields(paper).length" class="callout">
                              <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Fields</div>
                              <div class="mt-1 text-sm text-[var(--text-primary)]">{{ paperFields(paper).join(', ') }}</div>
                            </div>
                            <div v-if="paper.doi" class="callout">
                              <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">DOI</div>
                              <a
                                :href="`https://doi.org/${paper.doi}`"
                                target="_blank"
                                rel="noopener"
                                class="mt-1 block text-sm text-[var(--accent-primary)] hover:underline"
                              >
                                {{ paper.doi }}
                              </a>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>

            <div v-if="papers.length === 0" class="p-8 text-center text-[var(--text-muted)]">
              {{ totalPapers === 0 ? 'No papers yet. Approve and run a search plan to collect records.' : 'No papers match the current filters.' }}
            </div>

            <div v-if="filteredTotal > 0" class="flex flex-col gap-3 border-t border-white/8 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
              <div class="text-sm text-[var(--text-secondary)]">
                Showing {{ pageStart }}-{{ pageEnd }} of {{ filteredTotal }} filtered papers
              </div>

              <div class="flex flex-wrap items-center gap-2">
                <label class="text-sm text-[var(--text-secondary)]">Per page</label>
                <select v-model="pageSize" class="glass-input !min-h-[40px] w-[92px] text-sm">
                  <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
                </select>

                <button class="glass-btn" :disabled="currentPage <= 1" @click="goToPreviousPage">
                  Previous
                </button>
                <span class="capsule">Page {{ currentPage }} / {{ pageCount }}</span>
                <button class="glass-btn" :disabled="currentPage >= pageCount" @click="goToNextPage">
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-4">
          <CollapsibleInfoCard eyebrow="Curation notes" title="What to tighten before analysis">
            <div class="space-y-3">
              <div class="callout callout--accent">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Trim noise early</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Use source and discovery filters to remove low-signal batches before you generate charts.
                </div>
              </div>
              <div class="callout">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Protect traceability</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Expanded rows keep DOI, discovery method, and journal visible so you can justify why a paper is in scope.
                </div>
              </div>
            </div>
          </CollapsibleInfoCard>
        </div>
      </div>
    </template>
  </div>
</template>
