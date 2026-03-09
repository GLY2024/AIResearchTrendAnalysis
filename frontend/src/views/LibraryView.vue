<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { Paper } from '@/types'
import { paperApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import axios from 'axios'

const sessionStore = useSessionStore()
const papers = ref<Paper[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)
const selectedIds = ref<Set<number>>(new Set())

// Filters
const filterSource = ref('')
const filterDiscovery = ref('')
const filterYearFrom = ref<number | null>(null)
const filterYearTo = ref<number | null>(null)
const filterIncludedOnly = ref(false)
const searchQuery = ref('')
const sortKey = ref<'title' | 'year' | 'citation_count'>('citation_count')
const sortAsc = ref(false)

// Filter options loaded from backend
const availableSources = ref<string[]>([])
const availableMethods = ref<string[]>([])

async function loadPapers() {
  if (!sessionStore.currentSession) return
  loading.value = true
  try {
    papers.value = await paperApi.list(sessionStore.currentSession.id)
    // Load filter options
    const resp = await axios.get('/api/papers/sources', {
      params: { session_id: sessionStore.currentSession.id }
    })
    availableSources.value = resp.data.sources
    availableMethods.value = resp.data.discovery_methods
  } finally {
    loading.value = false
  }
}

const filteredPapers = computed(() => {
  let result = [...papers.value]

  if (filterSource.value) {
    result = result.filter(p => p.source === filterSource.value)
  }
  if (filterDiscovery.value) {
    result = result.filter(p => p.discovery_method === filterDiscovery.value)
  }
  if (filterYearFrom.value) {
    result = result.filter(p => (p.year ?? 0) >= filterYearFrom.value!)
  }
  if (filterYearTo.value) {
    result = result.filter(p => (p.year ?? 9999) <= filterYearTo.value!)
  }
  if (filterIncludedOnly.value) {
    result = result.filter(p => p.is_included)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(p =>
      p.title.toLowerCase().includes(q) ||
      p.abstract?.toLowerCase().includes(q) ||
      p.journal?.toLowerCase().includes(q) ||
      p.authors.some(a => a.name.toLowerCase().includes(q))
    )
  }

  result.sort((a, b) => {
    let cmp = 0
    if (sortKey.value === 'title') cmp = a.title.localeCompare(b.title)
    else if (sortKey.value === 'year') cmp = (a.year ?? 0) - (b.year ?? 0)
    else cmp = a.citation_count - b.citation_count
    return sortAsc.value ? cmp : -cmp
  })

  return result
})

function toggleSort(key: typeof sortKey.value) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = false
  }
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  // Force reactivity
  selectedIds.value = new Set(selectedIds.value)
}

function selectAll() {
  if (selectedIds.value.size === filteredPapers.value.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(filteredPapers.value.map(p => p.id))
  }
}

async function batchInclude(include: boolean) {
  if (selectedIds.value.size === 0) return
  await axios.post('/api/papers/batch-update', {
    paper_ids: [...selectedIds.value],
    is_included: include,
  })
  // Update local state
  for (const p of papers.value) {
    if (selectedIds.value.has(p.id)) {
      p.is_included = include
    }
  }
  selectedIds.value = new Set()
}

async function batchDelete() {
  if (selectedIds.value.size === 0) return
  if (!confirm(`Delete ${selectedIds.value.size} papers?`)) return
  await axios.post('/api/papers/batch-delete', {
    paper_ids: [...selectedIds.value],
  })
  papers.value = papers.value.filter(p => !selectedIds.value.has(p.id))
  selectedIds.value = new Set()
}

watch(() => sessionStore.currentSessionId, loadPapers)
onMounted(loadPapers)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <h1 class="text-xl font-semibold text-[var(--text-primary)]">Paper Library</h1>
      <div class="text-sm text-[var(--text-secondary)]">
        {{ filteredPapers.length }} papers
        <span v-if="papers.length !== filteredPapers.length"> of {{ papers.length }} total</span>
      </div>
    </div>

    <div v-if="!sessionStore.currentSession" class="text-[var(--text-muted)] mt-4">
      Select a session first.
    </div>

    <template v-else>
      <!-- Search bar -->
      <div class="mb-4">
        <input
          v-model="searchQuery"
          type="text"
          class="glass-input w-full"
          placeholder="Search papers by title, abstract, journal, or author..."
        />
      </div>

      <!-- Filters -->
      <div class="glass-card p-4 mb-4 flex flex-wrap gap-4 items-end">
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Source</label>
          <select v-model="filterSource" class="glass-input w-36">
            <option value="">All</option>
            <option v-for="s in availableSources" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Found via</label>
          <select v-model="filterDiscovery" class="glass-input w-40">
            <option value="">All</option>
            <option v-for="m in availableMethods" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Year from</label>
          <input v-model.number="filterYearFrom" type="number" class="glass-input w-24" placeholder="2020" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Year to</label>
          <input v-model.number="filterYearTo" type="number" class="glass-input w-24" placeholder="2025" />
        </div>
        <label class="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer">
          <input v-model="filterIncludedOnly" type="checkbox" class="accent-[var(--accent-primary)]" />
          Included only
        </label>
      </div>

      <!-- Batch actions -->
      <div v-if="selectedIds.size > 0" class="flex gap-2 mb-3 items-center">
        <span class="text-sm text-[var(--text-secondary)]">{{ selectedIds.size }} selected</span>
        <button class="glass-btn text-xs" @click="batchInclude(true)">Include</button>
        <button class="glass-btn text-xs" @click="batchInclude(false)">Exclude</button>
        <button class="glass-btn text-xs text-[var(--error)]" @click="batchDelete">Delete</button>
      </div>

      <div v-if="loading" class="text-[var(--text-muted)]">Loading papers...</div>

      <!-- Table -->
      <div v-else class="glass-card overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-white/10 text-left text-[var(--text-muted)]">
              <th class="p-3 w-10">
                <input
                  type="checkbox"
                  class="accent-[var(--accent-primary)]"
                  :checked="selectedIds.size > 0 && selectedIds.size === filteredPapers.length"
                  @change="selectAll"
                />
              </th>
              <th class="p-3 cursor-pointer hover:text-[var(--text-primary)]" @click="toggleSort('title')">
                Title {{ sortKey === 'title' ? (sortAsc ? '↑' : '↓') : '' }}
              </th>
              <th class="p-3 hidden md:table-cell">Authors</th>
              <th class="p-3 w-20 cursor-pointer hover:text-[var(--text-primary)]" @click="toggleSort('year')">
                Year {{ sortKey === 'year' ? (sortAsc ? '↑' : '↓') : '' }}
              </th>
              <th class="p-3 w-20 cursor-pointer hover:text-[var(--text-primary)]" @click="toggleSort('citation_count')">
                Cites {{ sortKey === 'citation_count' ? (sortAsc ? '↑' : '↓') : '' }}
              </th>
              <th class="p-3 w-24 hidden lg:table-cell">Source</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="paper in filteredPapers" :key="paper.id">
              <tr
                class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors"
                :class="{ 'bg-white/[0.03]': selectedIds.has(paper.id) }"
              >
                <td class="p-3" @click.stop>
                  <input
                    type="checkbox"
                    class="accent-[var(--accent-primary)]"
                    :checked="selectedIds.has(paper.id)"
                    @change="toggleSelect(paper.id)"
                  />
                </td>
                <td
                  class="p-3 text-[var(--text-primary)]"
                  @click="expandedId = expandedId === paper.id ? null : paper.id"
                >
                  <span v-if="paper.is_included" class="inline-block w-1.5 h-1.5 rounded-full bg-[var(--success)] mr-2" />
                  <span v-else class="inline-block w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] mr-2 opacity-40" />
                  {{ paper.title }}
                </td>
                <td
                  class="p-3 text-[var(--text-secondary)] hidden md:table-cell truncate max-w-[200px]"
                  @click="expandedId = expandedId === paper.id ? null : paper.id"
                >
                  {{ paper.authors.slice(0, 3).map(a => a.name).join(', ') }}
                  {{ paper.authors.length > 3 ? ` +${paper.authors.length - 3}` : '' }}
                </td>
                <td class="p-3 text-[var(--text-secondary)]">{{ paper.year ?? '-' }}</td>
                <td class="p-3 text-[var(--text-secondary)]">{{ paper.citation_count }}</td>
                <td class="p-3 text-[var(--text-muted)] hidden lg:table-cell">{{ paper.source ?? '-' }}</td>
              </tr>
              <!-- Expanded row -->
              <tr v-if="expandedId === paper.id">
                <td colspan="6" class="p-4 bg-white/[0.03]">
                  <div class="space-y-2 text-sm">
                    <p class="text-[var(--text-secondary)]">{{ paper.abstract || 'No abstract available.' }}</p>
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="kw in paper.keywords"
                        :key="kw"
                        class="badge badge-info"
                      >{{ kw }}</span>
                    </div>
                    <div class="text-xs text-[var(--text-muted)] flex flex-wrap gap-4">
                      <span v-if="paper.doi">DOI: {{ paper.doi }}</span>
                      <span v-if="paper.journal">Journal: {{ paper.journal }}</span>
                      <span v-if="paper.discovery_method">Found via: {{ paper.discovery_method }}</span>
                      <span v-if="paper.fields?.length">Fields: {{ paper.fields.join(', ') }}</span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <div v-if="filteredPapers.length === 0" class="p-8 text-center text-[var(--text-muted)]">
          {{ papers.length === 0 ? 'No papers yet. Run a search plan to collect papers.' : 'No papers match current filters.' }}
        </div>
      </div>
    </template>
  </div>
</template>
