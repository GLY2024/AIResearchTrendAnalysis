<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { Paper } from '@/types'
import { paperApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()
const papers = ref<Paper[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)

// Filters
const filterSource = ref('')
const filterYearFrom = ref<number | null>(null)
const filterYearTo = ref<number | null>(null)
const filterIncludedOnly = ref(false)
const sortKey = ref<'title' | 'year' | 'citation_count'>('year')
const sortAsc = ref(false)

async function loadPapers() {
  if (!sessionStore.currentSession) return
  loading.value = true
  try {
    papers.value = await paperApi.list(sessionStore.currentSession.id)
  } finally {
    loading.value = false
  }
}

const filteredPapers = computed(() => {
  let result = [...papers.value]

  if (filterSource.value) {
    result = result.filter(p => p.source === filterSource.value)
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

  result.sort((a, b) => {
    let cmp = 0
    if (sortKey.value === 'title') cmp = a.title.localeCompare(b.title)
    else if (sortKey.value === 'year') cmp = (a.year ?? 0) - (b.year ?? 0)
    else cmp = a.citation_count - b.citation_count
    return sortAsc.value ? cmp : -cmp
  })

  return result
})

const sources = computed(() => {
  const s = new Set(papers.value.map(p => p.source).filter(Boolean))
  return [...s] as string[]
})

function toggleSort(key: typeof sortKey.value) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = false
  }
}

watch(() => sessionStore.currentSessionId, loadPapers)
onMounted(loadPapers)
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-[var(--text-primary)] mb-1">Paper Library</h1>
    <p class="text-sm text-[var(--text-secondary)] mb-4">
      {{ filteredPapers.length }} papers
      <span v-if="papers.length !== filteredPapers.length"> of {{ papers.length }} total</span>
    </p>

    <div v-if="!sessionStore.currentSession" class="text-[var(--text-muted)]">
      Select a session first.
    </div>

    <template v-else>
      <!-- Filters -->
      <div class="glass-card p-4 mb-4 flex flex-wrap gap-4 items-end">
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Source</label>
          <select v-model="filterSource" class="glass-input w-40">
            <option value="">All</option>
            <option v-for="s in sources" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Year from</label>
          <input v-model.number="filterYearFrom" type="number" class="glass-input w-24" placeholder="e.g. 2020" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-muted)] mb-1">Year to</label>
          <input v-model.number="filterYearTo" type="number" class="glass-input w-24" placeholder="e.g. 2025" />
        </div>
        <label class="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer">
          <input v-model="filterIncludedOnly" type="checkbox" class="accent-[var(--accent-primary)]" />
          Included only
        </label>
      </div>

      <div v-if="loading" class="text-[var(--text-muted)]">Loading papers...</div>

      <!-- Table -->
      <div v-else class="glass-card overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-white/10 text-left text-[var(--text-muted)]">
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
                @click="expandedId = expandedId === paper.id ? null : paper.id"
              >
                <td class="p-3 text-[var(--text-primary)]">
                  <span v-if="paper.is_included" class="inline-block w-1.5 h-1.5 rounded-full bg-[var(--success)] mr-2" />
                  {{ paper.title }}
                </td>
                <td class="p-3 text-[var(--text-secondary)] hidden md:table-cell truncate max-w-[200px]">
                  {{ paper.authors.map(a => a.name).join(', ') }}
                </td>
                <td class="p-3 text-[var(--text-secondary)]">{{ paper.year ?? '-' }}</td>
                <td class="p-3 text-[var(--text-secondary)]">{{ paper.citation_count }}</td>
                <td class="p-3 text-[var(--text-muted)] hidden lg:table-cell">{{ paper.source ?? '-' }}</td>
              </tr>
              <!-- Expanded row -->
              <tr v-if="expandedId === paper.id">
                <td colspan="5" class="p-4 bg-white/[0.03]">
                  <div class="space-y-2 text-sm">
                    <p class="text-[var(--text-secondary)]">{{ paper.abstract || 'No abstract available.' }}</p>
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="kw in paper.keywords"
                        :key="kw"
                        class="badge badge-info"
                      >{{ kw }}</span>
                    </div>
                    <div class="text-xs text-[var(--text-muted)] flex gap-4">
                      <span v-if="paper.doi">DOI: {{ paper.doi }}</span>
                      <span v-if="paper.journal">Journal: {{ paper.journal }}</span>
                      <span v-if="paper.discovery_method">Found via: {{ paper.discovery_method }}</span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <div v-if="filteredPapers.length === 0" class="p-8 text-center text-[var(--text-muted)]">
          No papers match current filters.
        </div>
      </div>
    </template>
  </div>
</template>
