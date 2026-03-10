<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Report } from '@/types'
import { exportApi, reportApi } from '@/composables/useApi'
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
const exporting = ref<'ris' | 'bibtex' | ''>('')

const reportCount = computed(() => reports.value.length)
const completedCount = computed(() => reports.value.filter((report) => report.status === 'completed').length)
const latestVersion = computed(() => reports.value[0]?.version ?? 0)
const selectedWordCount = computed(() => wordCount(selectedReport.value?.content_markdown))

const statusBadge: Record<string, string> = {
  draft: 'badge-warning',
  generating: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-error',
}

async function loadReports() {
  if (!sessionStore.currentSession) return

  loading.value = true
  actionError.value = ''
  try {
    reports.value = await reportApi.list(sessionStore.currentSession.id)
    const firstReport = reports.value[0]
    if (firstReport && !selectedReport.value) selectedReport.value = firstReport
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
    void pollForCompletion(report.id)
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to generate the report.'
    await checkBackend(true)
  } finally {
    generating.value = false
  }
}

async function pollForCompletion(reportId: number) {
  const maxAttempts = 120
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5000))
    try {
      const updated = await reportApi.get(reportId)
      const index = reports.value.findIndex((report) => report.id === reportId)
      if (index !== -1) reports.value[index] = updated
      if (selectedReport.value?.id === reportId) {
        selectedReport.value = updated
      }
      if (updated.status === 'completed' || updated.status === 'failed') break
    } catch {
      break
    }
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

async function downloadExport(format: 'ris' | 'bibtex') {
  if (!sessionStore.currentSession) return

  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('export')
    showExportDialog.value = false
    return
  }

  const url = format === 'ris'
    ? exportApi.risUrl(sessionStore.currentSession.id)
    : exportApi.bibtexUrl(sessionStore.currentSession.id)

  exporting.value = format
  actionError.value = ''
  try {
    const response = await fetch(url, {
      headers: { Accept: 'text/plain' },
    })
    if (!response.ok) {
      throw new Error(`Export failed with HTTP ${response.status}`)
    }

    const content = await response.text()
    const blob = new Blob([content], {
      type: format === 'ris' ? 'application/x-research-info-systems' : 'application/x-bibtex',
    })
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = `session_${sessionStore.currentSession.id}.${format === 'ris' ? 'ris' : 'bib'}`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(objectUrl)
    showExportDialog.value = false
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to export papers.'
    await checkBackend(true)
  } finally {
    exporting.value = ''
  }
}

watch(() => sessionStore.currentSessionId, () => {
  selectedReport.value = null
  void loadReports()
})

onMounted(loadReports)
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Publishing</div>
      <h2 class="page-hero__title">Turn the curated corpus into a presentation-ready narrative.</h2>
      <p class="page-hero__copy">
        The report room now works as a final review surface, with report versions on the left and the live draft on the right.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Reports</span>
          <span class="stat-card__value">{{ reportCount }}</span>
          <span class="stat-card__hint">Saved versions in this session</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Completed</span>
          <span class="stat-card__value">{{ completedCount }}</span>
          <span class="stat-card__hint">Versions ready to present or export</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Latest version</span>
          <span class="stat-card__value">{{ latestVersion }}</span>
          <span class="stat-card__hint">Highest report revision number</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Selected size</span>
          <span class="stat-card__value text-[1.1rem]">{{ selectedWordCount }}</span>
          <span class="stat-card__hint">Approximate word count of the open report</span>
        </div>
      </div>
    </section>

    <div v-if="!sessionStore.currentSession" class="surface-panel p-8">
      <h3 class="surface-panel__title">Select a session first.</h3>
      <p class="surface-panel__copy mt-3">
        Report generation depends on the session library and completed analyses.
      </p>
    </div>

    <template v-else>
      <div
        v-if="actionError"
        class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          class="glass-btn"
          :disabled="!sessionStore.currentSession || backendState.status !== 'online'"
          @click="showExportDialog = true"
        >
          Export papers
        </button>
        <button
          class="glass-btn glass-btn-primary"
          :disabled="generating || !sessionStore.currentSession || backendState.status !== 'online'"
          @click="generateReport()"
        >
          {{ generating ? 'Generating report...' : 'Generate report' }}
        </button>
      </div>

      <div class="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <div class="space-y-4">
          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Version list</p>
                  <h3 class="surface-panel__title">Report revisions</h3>
                </div>
              </div>
            </template>

            <div v-if="loading" class="space-y-2">
              <SkeletonCard v-for="index in 3" :key="index" height="80px" :lines="2" />
            </div>

            <div v-else-if="reports.length === 0" class="text-sm text-[var(--text-muted)]">
              No reports yet. Generate the first version once your library and analyses are ready.
            </div>

            <div v-else class="space-y-3">
              <button
                v-for="report in reports"
                :key="report.id"
                class="glass-card glass-card--interactive w-full p-4 text-left"
                :class="selectedReport?.id === report.id ? 'border-[var(--accent-primary)]/35 bg-[var(--accent-primary)]/8' : ''"
                @click="selectReport(report)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-semibold text-[var(--text-primary)]">
                      {{ report.title || `Report v${report.version}` }}
                    </div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <span :class="['badge', statusBadge[report.status]]">{{ report.status }}</span>
                      <span class="capsule">v{{ report.version }}</span>
                    </div>
                  </div>
                  <div class="text-[11px] text-[var(--text-muted)]">
                    {{ wordCount(report.content_markdown) }} words
                  </div>
                </div>
                <div class="mt-3 text-[11px] text-[var(--text-muted)]">
                  {{ new Date(report.created_at).toLocaleString() }}
                </div>
              </button>
            </div>
          </GlassCard>

          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Presentation note</p>
                  <h3 class="surface-panel__title">How to narrate the output</h3>
                </div>
              </div>
            </template>

            <div class="space-y-3">
              <div class="callout callout--accent">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Lead with structure, not prose</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Show the charts and section headings first, then zoom into the AI-written interpretation.
                </div>
              </div>
              <div class="callout">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Keep versions visible</div>
                <div class="mt-1 text-sm text-[var(--text-secondary)]">
                  Version cards make iterative report updates easier to explain during the demo.
                </div>
              </div>
            </div>
          </GlassCard>
        </div>

        <GlassCard v-if="selectedReport" class="min-w-0">
          <template #header>
            <div class="surface-panel__header !mb-0">
              <div>
                <p class="surface-panel__eyebrow">Open report</p>
                <div class="flex flex-wrap items-center gap-3">
                  <h3 class="surface-panel__title">
                    {{ selectedReport.title || `Report v${selectedReport.version}` }}
                  </h3>
                  <span :class="['badge', statusBadge[selectedReport.status]]">{{ selectedReport.status }}</span>
                </div>
              </div>

              <button
                v-if="selectedReport.status === 'completed'"
                class="glass-btn"
                :disabled="generating || backendState.status !== 'online'"
                @click="generateReport(selectedReport.id)"
              >
                Update report
              </button>
            </div>
          </template>

          <div v-if="selectedReport.status === 'generating'" class="space-y-4">
            <div class="streaming-bar w-full" />
            <div class="text-sm text-[var(--text-secondary)]">
              Generating the report. This may take a minute.
            </div>
          </div>

          <div v-else-if="selectedReport.status === 'failed'" class="text-sm text-[var(--error)]">
            {{ selectedReport.content_markdown || 'Report generation failed.' }}
          </div>

          <template v-else>
            <div class="md-content">
              <StreamingText
                :text="selectedReport.content_markdown || ''"
                :is-streaming="false"
              />
            </div>

            <template v-for="(chartGroup, groupIndex) in selectedReport.chart_configs" :key="groupIndex">
              <div
                v-if="Array.isArray(chartGroup) && chartGroup.length"
                class="my-6 grid grid-cols-1 gap-5 xl:grid-cols-2"
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

    <Teleport to="body">
      <div v-if="showExportDialog" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/65 backdrop-blur-sm" @click="showExportDialog = false" />
        <div class="surface-panel relative z-10 w-[360px] p-6">
          <h3 class="section-heading">Export papers</h3>
          <p class="section-copy mb-4">Choose the bibliography format that best fits your workflow.</p>

          <div class="space-y-3">
            <button class="glass-btn w-full justify-center" :disabled="exporting !== ''" @click="downloadExport('ris')">
              {{ exporting === 'ris' ? 'Exporting RIS...' : 'Export as RIS' }}
            </button>
            <button class="glass-btn w-full justify-center" :disabled="exporting !== ''" @click="downloadExport('bibtex')">
              {{ exporting === 'bibtex' ? 'Exporting BibTeX...' : 'Export as BibTeX' }}
            </button>
          </div>

          <button class="mt-4 text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)]" @click="showExportDialog = false">
            Cancel
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
