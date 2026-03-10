<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { Report } from '@/types'
import { reportApi, exportApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'
import StreamingText from '@/components/chat/StreamingText.vue'
import ChartContainer from '@/components/common/ChartContainer.vue'
import SkeletonCard from '@/components/common/SkeletonCard.vue'

const sessionStore = useSessionStore()
const backendState = useBackendState()
const reports = ref<Report[]>([])
const selectedReport = ref<Report | null>(null)
const loading = ref(false)
const generating = ref(false)
const showExportDialog = ref(false)
const actionError = ref('')

async function loadReports() {
  if (!sessionStore.currentSession) return
  loading.value = true
  actionError.value = ''
  try {
    reports.value = await reportApi.list(sessionStore.currentSession.id)
    const firstReport = reports.value[0]
    if (firstReport && !selectedReport.value) {
      selectedReport.value = firstReport
    }
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load reports.'
    await checkBackend(true)
  } finally {
    loading.value = false
  }
}

async function generateReport(parentId?: number) {
  if (!sessionStore.currentSession) return
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('report generation')
    return
  }
  generating.value = true
  try {
    const report = await reportApi.generate({
      session_id: sessionStore.currentSession.id,
      parent_report_id: parentId,
    })
    reports.value.unshift(report)
    selectedReport.value = report
    pollForCompletion(report.id)
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to generate the report.'
    await checkBackend(true)
  } finally {
    generating.value = false
  }
}

async function pollForCompletion(reportId: number) {
  const maxAttempts = 120
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 5000))
    try {
      const updated = await reportApi.get(reportId)
      const idx = reports.value.findIndex(r => r.id === reportId)
      if (idx !== -1) reports.value[idx] = updated
      if (selectedReport.value?.id === reportId) {
        selectedReport.value = updated
      }
      if (updated.status === 'completed' || updated.status === 'failed') break
    } catch { break }
  }
}

function selectReport(report: Report) {
  selectedReport.value = report
}

function wordCount(text: string | null | undefined): string {
  if (!text) return '0'
  const count = text.split(/\s+/).filter(Boolean).length
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
  return String(count)
}

function downloadExport(format: 'ris' | 'bibtex') {
  if (!sessionStore.currentSession) return
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('export')
    showExportDialog.value = false
    return
  }

  const url = format === 'ris'
    ? exportApi.risUrl(sessionStore.currentSession.id)
    : exportApi.bibtexUrl(sessionStore.currentSession.id)
  window.open(url, '_blank')
  showExportDialog.value = false
}

const statusBadge: Record<string, string> = {
  draft: 'badge-warning',
  generating: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
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
        <p class="text-sm text-[var(--text-secondary)] mt-1">
          Generate and view research trend reports.
        </p>
      </div>
      <div class="flex gap-3">
        <button
          class="glass-btn"
          :disabled="!sessionStore.currentSession || backendState.status !== 'online'"
          @click="showExportDialog = true"
        >
          Export
        </button>
        <button
          class="glass-btn glass-btn-primary"
          :disabled="generating || !sessionStore.currentSession || backendState.status !== 'online'"
          @click="generateReport()"
        >
          <span v-if="generating" class="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin mr-2" />
          Generate Report
        </button>
      </div>
    </div>

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

      <!-- Loading skeleton -->
      <div v-if="loading" class="flex gap-6">
        <div class="w-56 shrink-0 space-y-2">
          <SkeletonCard v-for="i in 3" :key="i" height="80px" :lines="2" />
        </div>
        <SkeletonCard class="flex-1" height="400px" :lines="8" />
      </div>

      <div v-else-if="reports.length === 0" class="text-[var(--text-muted)]">
        No reports yet. Click "Generate Report" to create one.
      </div>

      <div v-else class="flex gap-6">
        <!-- Report list sidebar -->
        <div class="w-56 shrink-0 space-y-2">
          <div
            v-for="report in reports"
            :key="report.id"
            class="glass-card p-3 cursor-pointer transition-all"
            :class="selectedReport?.id === report.id ? 'border border-[var(--accent-primary)]/50' : ''"
            @click="selectReport(report)"
          >
            <div class="text-sm font-medium text-[var(--text-primary)] truncate">
              {{ report.title || `Report v${report.version}` }}
            </div>
            <div class="flex items-center justify-between mt-1.5">
              <span :class="['badge text-[10px]', statusBadge[report.status]]">
                {{ report.status }}
              </span>
              <span class="text-[10px] text-[var(--text-muted)]">
                v{{ report.version }}
              </span>
            </div>
            <div class="flex items-center justify-between mt-1.5 text-[10px] text-[var(--text-muted)]">
              <span>{{ new Date(report.created_at).toLocaleDateString() }}</span>
              <span>{{ wordCount(report.content_markdown) }} words</span>
            </div>
          </div>
        </div>

        <!-- Report content -->
        <GlassCard v-if="selectedReport" class="flex-1 min-w-0">
          <div class="flex items-center justify-between mb-5">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">
              {{ selectedReport.title || `Report v${selectedReport.version}` }}
            </h2>
            <button
              v-if="selectedReport.status === 'completed'"
              class="glass-btn text-xs"
              :disabled="generating || backendState.status !== 'online'"
              @click="generateReport(selectedReport.id)"
            >
              Update Report
            </button>
          </div>

          <!-- Generating state -->
          <div v-if="selectedReport.status === 'generating'" class="space-y-3">
            <div class="streaming-bar w-full" />
            <div class="flex items-center gap-3 text-[var(--text-secondary)]">
              <span class="inline-block w-4 h-4 rounded-full border-2 border-white/20 border-t-[var(--accent-primary)] animate-spin" />
              Generating report... This may take a minute.
            </div>
          </div>

          <!-- Failed state -->
          <div v-else-if="selectedReport.status === 'failed'" class="text-[var(--error)]">
            {{ selectedReport.content_markdown || 'Report generation failed.' }}
          </div>

          <!-- Markdown content + charts -->
          <template v-else>
            <div class="md-content">
              <StreamingText
                :text="selectedReport.content_markdown || ''"
                :is-streaming="false"
              />
            </div>

            <!-- Embedded charts -->
            <template v-for="(chartGroup, gi) in selectedReport.chart_configs" :key="gi">
              <div
                v-if="Array.isArray(chartGroup) && chartGroup.length"
                class="grid grid-cols-1 lg:grid-cols-2 gap-5 my-6"
              >
                <ChartContainer
                  v-for="chart in chartGroup"
                  :key="chart.id"
                  :option="chart.option"
                  :title="chart.title"
                  height="400px"
                />
              </div>
            </template>
          </template>
        </GlassCard>
      </div>
    </template>

    <!-- Export Dialog -->
    <Teleport to="body">
      <div v-if="showExportDialog" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showExportDialog = false" />
        <div class="glass-card p-6 relative z-10 w-80">
          <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">Export Papers</h3>
          <div class="space-y-3">
            <button class="glass-btn w-full justify-center" @click="downloadExport('ris')">
              Export as RIS
            </button>
            <button class="glass-btn w-full justify-center" @click="downloadExport('bibtex')">
              Export as BibTeX
            </button>
          </div>
          <button
            class="mt-4 text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            @click="showExportDialog = false"
          >
            Cancel
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
