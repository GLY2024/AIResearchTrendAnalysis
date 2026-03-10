<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { ChatMessage as ChatMessageType, SnowballCandidate, SnowballRun } from '@/types'
import { chatApi, searchApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { useWebSocket } from '@/composables/useWebSocket'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import GlassCard from '@/components/common/GlassCard.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

interface WorkflowFeedItem {
  id: string
  title: string
  detail: string
  tone: 'neutral' | 'accent' | 'success' | 'warning' | 'error'
  updatedAt: string
}

const router = useRouter()
const sessionStore = useSessionStore()
const backendState = useBackendState()

const messages = ref<ChatMessageType[]>([])
const loading = ref(false)
const streaming = ref(false)
const streamingContent = ref('')
const scrollContainer = ref<HTMLElement | null>(null)
const planGenerating = ref(false)
const actionError = ref('')
const needsApiKey = ref(false)
const workflowFeed = ref<WorkflowFeedItem[]>([])
const currentSnowballRun = ref<SnowballRun | null>(null)
const snowballPreview = ref<SnowballCandidate[]>([])
const snowballBusyAction = ref('')
const selectedSnowballIds = ref<Set<number>>(new Set())

let ws: ReturnType<typeof useWebSocket> | null = null
let localMessageCounter = 0

const suggestedTopics = [
  'Map the latest trends in large language model agents for scientific discovery.',
  'Summarize the strongest 2024-2026 papers on hallucination detection in LLMs.',
  'Draft a focused literature review plan for multimodal reasoning benchmarks.',
]

const workflowSteps = [
  { title: 'Frame the topic', copy: 'Use the chat to sharpen scope, years, venues, and assumptions before collecting papers.' },
  { title: 'Generate a plan', copy: 'Create a search strategy directly from the current session once the topic is crisp enough.' },
  { title: 'Move downstream', copy: 'Approve the search, curate the library, then run analysis and report generation.' },
]

const sessionMessageCount = computed(() => messages.value.length + (streaming.value && streamingContent.value ? 1 : 0))
const assistantMessageCount = computed(() => messages.value.filter((message) => message.role === 'assistant').length)
const currentPaperCount = computed(() => sessionStore.currentSession?.paper_count ?? 0)
const selectedSnowballCount = computed(() => selectedSnowballIds.value.size)

const liveStatus = computed(() => {
  if (snowballBusyAction.value) {
    return { label: 'Snowball', detail: 'Reviewing or importing snowball candidates.' }
  }
  if (planGenerating.value) {
    return { label: 'Planning', detail: 'The planner is drafting a search strategy.' }
  }
  if (streaming.value) {
    return { label: 'Streaming', detail: 'The assistant is responding token by token.' }
  }
  if (loading.value) {
    return { label: 'Thinking', detail: 'ARTA is processing the current request.' }
  }
  if (backendState.status === 'online') {
    return { label: 'Ready', detail: 'Live chat, workflow telemetry, and approvals are available.' }
  }
  if (backendState.status === 'checking') {
    return { label: 'Checking', detail: 'Trying to reconnect to the local backend.' }
  }
  return { label: 'Offline', detail: 'Start the backend to restore chat and planning.' }
})

const inputDisabled = computed(() => loading.value || streaming.value || backendState.status !== 'online')

const inputPlaceholder = computed(() => {
  if (backendState.status !== 'online') {
    return 'Backend offline. Start the backend to send messages.'
  }
  return 'Ask for framing, critique, synthesis, or type /plan [topic].'
})

function nextLocalMessageId() {
  localMessageCounter += 1
  return Date.now() + localMessageCounter
}

function appendSystemMessage(content: string) {
  if (!sessionStore.currentSession) return
  messages.value.push({
    id: nextLocalMessageId(),
    session_id: sessionStore.currentSession.id,
    role: 'system',
    content,
    created_at: new Date().toISOString(),
  })
  void nextTick(scrollToBottom)
}

function upsertWorkflowFeed(id: string, title: string, detail: string, tone: WorkflowFeedItem['tone'] = 'neutral') {
  const updatedAt = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const index = workflowFeed.value.findIndex((item) => item.id === id)
  const nextItem: WorkflowFeedItem = { id, title, detail, tone, updatedAt }
  if (index === -1) {
    workflowFeed.value.unshift(nextItem)
    workflowFeed.value = workflowFeed.value.slice(0, 10)
    return
  }
  workflowFeed.value[index] = nextItem
}

function clearRuntimeState() {
  workflowFeed.value = []
  currentSnowballRun.value = null
  snowballPreview.value = []
  selectedSnowballIds.value = new Set()
  snowballBusyAction.value = ''
}

async function refreshSessionStats() {
  try {
    await sessionStore.fetchSessions()
  } catch {
    // Session refresh should not break the chat surface.
  }
}

async function fetchSnowballPreview(runId: number) {
  try {
    snowballPreview.value = await searchApi.listSnowballCandidates(runId, { status: 'pending', limit: 8 })
    selectedSnowballIds.value = new Set()
  } catch {
    snowballPreview.value = []
  }
}

async function refreshSnowballRun(runId: number) {
  try {
    currentSnowballRun.value = await searchApi.getSnowballRun(runId)
    if (currentSnowballRun.value.status === 'awaiting_review') {
      await fetchSnowballPreview(runId)
    } else if (currentSnowballRun.value.status === 'completed' || currentSnowballRun.value.status === 'rejected') {
      snowballPreview.value = []
      selectedSnowballIds.value = new Set()
    }
  } catch {
    currentSnowballRun.value = null
  }
}

async function loadSnowballState() {
  if (!sessionStore.currentSession) return
  try {
    const runs = await searchApi.listSnowballRuns(sessionStore.currentSession.id)
    currentSnowballRun.value = runs[0] ?? null
    if (currentSnowballRun.value?.status === 'awaiting_review') {
      await fetchSnowballPreview(currentSnowballRun.value.id)
    }
  } catch {
    currentSnowballRun.value = null
  }
}

function toggleSnowballCandidate(id: number) {
  const next = new Set(selectedSnowballIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedSnowballIds.value = next
}

async function handleSnowballAction(action: 'prepare_review' | 'approve_all' | 'approve_high_confidence' | 'approve_selected' | 'reject_selected' | 'reject') {
  if (!currentSnowballRun.value) return
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('snowball review')
    return
  }

  const candidateIds = ['approve_selected', 'reject_selected'].includes(action)
    ? [...selectedSnowballIds.value]
    : undefined

  if ((action === 'approve_selected' || action === 'reject_selected') && (!candidateIds || candidateIds.length === 0)) {
    actionError.value = 'Select at least one snowball candidate first.'
    return
  }

  snowballBusyAction.value = action
  actionError.value = ''
  try {
    await searchApi.snowballAction(currentSnowballRun.value.id, {
      action,
      candidate_ids: candidateIds,
    })

    if (action === 'reject') {
      appendSystemMessage('Snowball proposal rejected. The workflow will continue with the base search results only.')
      currentSnowballRun.value.status = 'rejected'
      snowballPreview.value = []
      selectedSnowballIds.value = new Set()
      return
    }

    if (action === 'prepare_review') {
      appendSystemMessage('Snowball review requested. ARTA is now collecting, screening, and verifying candidate papers.')
    } else if (action === 'approve_high_confidence') {
      appendSystemMessage('Snowball high-confidence import requested. ARTA will only import the strongest screened candidates.')
    } else if (action === 'approve_all') {
      appendSystemMessage('Snowball full import requested. ARTA will import every screened candidate that passes verification.')
    } else if (action === 'approve_selected') {
      appendSystemMessage(`Requested import for ${candidateIds?.length ?? 0} selected snowball candidates.`)
    } else if (action === 'reject_selected') {
      appendSystemMessage(`Rejected ${candidateIds?.length ?? 0} selected snowball candidates.`)
      selectedSnowballIds.value = new Set()
      await refreshSnowballRun(currentSnowballRun.value.id)
    }
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Snowball action failed.'
    await checkBackend(true)
  } finally {
    snowballBusyAction.value = ''
  }
}

async function handleRetryMessage(message: ChatMessageType) {
  actionError.value = ''
  try {
    const reply = await chatApi.retryMessage(message.id)
    const current = messages.value.find((item) => item.id === message.id)
    if (current?.metadata) {
      current.metadata = { ...current.metadata, retried: true }
    }
    messages.value.push(reply)
    await nextTick()
    scrollToBottom()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to retry this assistant message.'
    await checkBackend(true)
  }
}

async function handleDeleteMessage(message: ChatMessageType) {
  actionError.value = ''
  try {
    await chatApi.deleteMessage(message.id)
    messages.value = messages.value.filter((item) => item.id !== message.id)
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to delete this assistant message.'
    await checkBackend(true)
  }
}

function setupWebSocket() {
  if (ws) ws.disconnect()
  if (!sessionStore.currentSession) return

  ws = useWebSocket(sessionStore.currentSession.id)

  ws.on('chat_token', (data: Record<string, unknown>) => {
    streaming.value = true
    loading.value = false
    streamingContent.value += (data.token as string) || ''
    nextTick(scrollToBottom)
  })

  ws.on('chat_complete', (data: Record<string, unknown>) => {
    const message = data.message as ChatMessageType
    if (message) messages.value.push(message)
    streaming.value = false
    streamingContent.value = ''
    nextTick(scrollToBottom)
  })

  ws.on('plan_generating', () => {
    planGenerating.value = true
    upsertWorkflowFeed('plan-generating', 'Search plan', 'Drafting queries, criteria, and execution strategy.', 'accent')
  })

  ws.on('plan_generated', (data: Record<string, unknown>) => {
    planGenerating.value = false
    upsertWorkflowFeed('plan-generating', 'Search plan', 'Search plan is ready for review.', 'success')
    messages.value.push({
      id: nextLocalMessageId(),
      session_id: sessionStore.currentSession!.id,
      role: 'assistant',
      content: `Search plan generated for "${(data.plan_data as Record<string, string>)?.topic ?? 'the topic'}". Open the Search Plan view to review and approve it.`,
      created_at: new Date().toISOString(),
    })
    nextTick(scrollToBottom)
  })

  ws.on('search_progress', (data: Record<string, unknown>) => {
    const planId = data.plan_id as number
    const source = (data.source as string) || 'source'
    const status = (data.status as string) || 'running'
    const totalFound = data.total_found as number | undefined
    upsertWorkflowFeed(
      `search-${planId}`,
      `Search | ${source}`,
      `${status === 'failed' ? 'Failed' : 'Running'} | ${totalFound ?? 0} papers accumulated`,
      status === 'failed' ? 'error' : 'neutral',
    )
  })

  ws.on('search_complete', (data: Record<string, unknown>) => {
    const planId = data.plan_id as number
    const totalPapers = data.total_papers as number
    upsertWorkflowFeed(`search-${planId}`, 'Search', `Base search completed with ${totalPapers} papers.`, 'success')
    appendSystemMessage(`Base search completed. ${totalPapers} papers were collected. If snowball is enabled, ARTA will prepare a proposal instead of expanding automatically.`)
    void refreshSessionStats()
  })

  ws.on('snowball_proposed', (data: Record<string, unknown>) => {
    const runId = data.run_id as number | undefined
    const summary = data.proposal_summary as Record<string, unknown> | undefined
    upsertWorkflowFeed(
      `snowball-${runId ?? 'proposal'}`,
      'Snowball proposal',
      `Awaiting approval | budget ${summary?.estimated_candidate_budget ?? 0} candidates`,
      'warning',
    )
    appendSystemMessage(`Snowball proposal ready. Estimated candidate budget: ${summary?.estimated_candidate_budget ?? 0}. Review the seed papers and choose whether to skip, review, or import high-confidence candidates.`)
    if (runId) void refreshSnowballRun(runId)
  })

  ws.on('snowball_progress', (data: Record<string, unknown>) => {
    const runId = data.run_id as number
    const step = (data.step as string) || 'running'
    const candidateCount = data.candidate_count as number | undefined
    upsertWorkflowFeed(
      `snowball-${runId}`,
      'Snowball',
      `${step} | ${candidateCount ?? 0} candidates in flight`,
      'accent',
    )
  })

  ws.on('snowball_review_ready', (data: Record<string, unknown>) => {
    const runId = data.run_id as number
    const stats = data.stats as Record<string, number> | undefined
    upsertWorkflowFeed(
      `snowball-${runId}`,
      'Snowball review',
      `Review ready | ${stats?.candidate_count ?? 0} candidates, ${stats?.high_confidence_count ?? 0} high-confidence`,
      'warning',
    )
    appendSystemMessage(`Snowball review is ready. ${stats?.candidate_count ?? 0} candidates were staged, with ${stats?.high_confidence_count ?? 0} marked as high-confidence.`)
    void refreshSnowballRun(runId)
  })

  ws.on('snowball_complete', (data: Record<string, unknown>) => {
    const runId = data.run_id as number
    const importedCount = data.imported_count as number
    upsertWorkflowFeed(`snowball-${runId}`, 'Snowball', `Completed | ${importedCount} candidates imported`, 'success')
    appendSystemMessage(`Snowball import completed. ${importedCount} candidates were added to the library.`)
    void refreshSnowballRun(runId)
    void refreshSessionStats()
  })

  ws.on('snowball_rejected', (data: Record<string, unknown>) => {
    const runId = data.run_id as number
    upsertWorkflowFeed(`snowball-${runId}`, 'Snowball', 'Proposal rejected by the user.', 'warning')
  })

  ws.on('analysis_progress', (data: Record<string, unknown>) => {
    const runId = data.run_id as number
    const step = (data.step as string) || 'running'
    const analysisType = (data.analysis_type as string) || 'analysis'
    upsertWorkflowFeed(`analysis-${runId}`, `Analysis | ${analysisType}`, step, step === 'completed' ? 'success' : 'neutral')
  })

  ws.on('report_progress', (data: Record<string, unknown>) => {
    const reportId = data.report_id as number
    const step = (data.step as string) || 'running'
    upsertWorkflowFeed(`report-${reportId}`, 'Report', step, step === 'completed' ? 'success' : 'accent')
  })

  ws.on('error', (data: Record<string, unknown>) => {
    loading.value = false
    planGenerating.value = false

    if (data.error_code === 'no_api_key') {
      needsApiKey.value = true
      actionError.value = (data.message as string) || 'API key not configured.'
      appendSystemMessage(actionError.value)
      return
    }

    const message = (data.message as string) || 'An unexpected workflow error occurred.'
    if (data.scope === 'chat' && typeof data.message_id === 'number') {
      actionError.value = message
      upsertWorkflowFeed(`error-${data.message_id}`, 'Workflow error', message, 'error')
      return
    }

    streaming.value = false
    if (streamingContent.value) streamingContent.value = ''
    upsertWorkflowFeed(`error-${nextLocalMessageId()}`, 'Workflow error', message, 'error')
    appendSystemMessage(message)
  })
}

async function loadMessages() {
  if (!sessionStore.currentSession) return
  actionError.value = ''
  clearRuntimeState()

  try {
    messages.value = await chatApi.getMessages(sessionStore.currentSession.id)
    await loadSnowballState()
    await nextTick()
    scrollToBottom()
    setupWebSocket()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load chat history.'
    await checkBackend(true)
  }
}

function scrollToBottom() {
  if (!scrollContainer.value) return
  scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
}

async function handleSend(content: string) {
  actionError.value = ''
  if (!sessionStore.currentSession) {
    actionError.value = 'Select or create a session before sending messages.'
    return
  }

  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('chat')
    return
  }

  const planCommand = content.match(/^\/plan\s+(.+)/i)
  const userMessage: ChatMessageType = {
    id: nextLocalMessageId(),
    session_id: sessionStore.currentSession.id,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  }

  messages.value.push(userMessage)
  await nextTick()
  scrollToBottom()

  if (planCommand && ws?.connected.value) {
    ws.send('generate_plan', { topic: planCommand[1] })
    return
  }

  if (planCommand) {
    actionError.value = 'Search plan generation requires a live backend WebSocket connection.'
    await checkBackend(true)
    return
  }

  if (ws && ws.connected.value) {
    loading.value = true
    streamingContent.value = ''
    if (!ws.send('chat_send', { content })) {
      loading.value = false
      actionError.value = 'Live chat connection dropped before the message could be sent.'
      await checkBackend(true)
    }
    return
  }

  loading.value = true
  try {
    const reply = await chatApi.send({
      session_id: sessionStore.currentSession.id,
      content,
    })
    messages.value.push(reply)
  } catch {
    actionError.value = 'Failed to reach the backend. Your message was not processed.'
    await checkBackend(true)
    messages.value.push({
      id: nextLocalMessageId(),
      session_id: sessionStore.currentSession.id,
      role: 'assistant',
      content: 'Backend is offline or unreachable. Start it and try again.',
      created_at: new Date().toISOString(),
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleSuggestedPrompt(topic: string) {
  if (inputDisabled.value) return
  void handleSend(topic)
}

function handleGeneratePlan() {
  actionError.value = ''
  if (!sessionStore.currentSession || !ws) {
    actionError.value = 'Select a session before generating a search plan.'
    return
  }

  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('search plan generation')
    return
  }

  const topic = sessionStore.currentSession.title
  if (!ws.connected.value || !ws.send('generate_plan', { topic })) {
    actionError.value = 'Search plan generation requires a live backend WebSocket connection.'
    void checkBackend(true)
  }
}

watch(() => sessionStore.currentSessionId, loadMessages)

onMounted(loadMessages)

onUnmounted(() => {
  if (ws) ws.disconnect()
})
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Conversation workspace</div>
      <h2 class="page-hero__title">Turn a topic into a defensible research pipeline.</h2>
      <p class="page-hero__copy">
        Use the assistant to frame the scope, pressure-test assumptions, and decide when the topic is ready for plan generation.
        This page now behaves like a working cockpit instead of a plain chat log.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Messages</span>
          <span class="stat-card__value">{{ sessionMessageCount }}</span>
          <span class="stat-card__hint">Across the current session conversation</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Assistant replies</span>
          <span class="stat-card__value">{{ assistantMessageCount }}</span>
          <span class="stat-card__hint">Helps you gauge how mature the discussion is</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Collected papers</span>
          <span class="stat-card__value">{{ currentPaperCount }}</span>
          <span class="stat-card__hint">Current corpus count linked to this session</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Live status</span>
          <span class="stat-card__value text-[1.15rem]">{{ liveStatus.label }}</span>
          <span class="stat-card__hint">{{ liveStatus.detail }}</span>
        </div>
      </div>
    </section>

    <div v-if="!sessionStore.currentSession" class="surface-panel p-8">
      <div class="surface-panel__header">
        <div>
          <p class="surface-panel__eyebrow">Session required</p>
          <h3 class="surface-panel__title">Create or select a session to start the live demo.</h3>
        </div>
      </div>
      <p class="surface-panel__copy">
        Sessions hold the conversation, the search plan, the paper library, downstream analysis, and generated reports.
      </p>
    </div>

    <template v-else>
      <div v-if="needsApiKey" class="callout callout--accent">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="text-sm font-semibold text-[var(--text-primary)]">Provider configuration required</div>
            <div class="mt-1 text-sm text-[var(--text-secondary)]">
              {{ actionError || 'Configure at least one model provider before using chat and planning.' }}
            </div>
          </div>
          <button class="glass-btn glass-btn-primary" @click="router.push('/settings'); needsApiKey = false; actionError = ''">
            Open settings
          </button>
        </div>
      </div>

      <div
        v-else-if="actionError"
        class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_360px]">
        <GlassCard :padding="false" class="min-h-[720px]">
          <div class="flex h-full min-h-[720px] flex-col">
            <div class="flex flex-col gap-4 border-b border-white/8 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p class="surface-panel__eyebrow">Current session</p>
                <h3 class="surface-panel__title">{{ sessionStore.currentSession.title }}</h3>
                <p class="surface-panel__copy mt-2">
                  {{ liveStatus.detail }}
                </p>
              </div>

              <div class="flex flex-wrap gap-3">
                <span class="capsule">
                  <span class="inline-block h-2 w-2 rounded-full bg-[var(--accent-primary)]" />
                  {{ liveStatus.label }}
                </span>
                <button
                  class="glass-btn glass-btn-primary"
                  :disabled="planGenerating || backendState.status !== 'online'"
                  @click="handleGeneratePlan"
                >
                  {{ planGenerating ? 'Generating plan...' : 'Generate search plan' }}
                </button>
              </div>
            </div>

            <div ref="scrollContainer" class="flex-1 space-y-4 overflow-y-auto px-6 py-6">
              <div
                v-if="messages.length === 0 && !loading && !streaming"
                class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]"
              >
                <div class="rounded-[26px] border border-dashed border-white/12 bg-white/[0.03] p-6">
                  <div class="page-hero__kicker">Start here</div>
                  <h4 class="section-heading">Kick off the literature workflow with a strong first prompt.</h4>
                  <p class="section-copy">
                    Ask for scope refinement, benchmark landscape, venue suggestions, or prompt the assistant to produce a search plan directly.
                  </p>
                  <div class="mt-5 space-y-2">
                    <button
                      v-for="topic in suggestedTopics"
                      :key="topic"
                      class="glass-btn w-full justify-start text-left !h-auto !py-3"
                      @click="handleSuggestedPrompt(topic)"
                    >
                      {{ topic }}
                    </button>
                  </div>
                </div>

                <div class="callout">
                  <div class="text-sm font-semibold text-[var(--text-primary)]">Shortcut</div>
                  <div class="mt-2 text-sm text-[var(--text-secondary)]">
                    Type <code class="rounded bg-white/8 px-1.5 py-0.5 text-[var(--accent-primary)]">/plan [topic]</code>
                    to generate a search plan without leaving this page.
                  </div>
                </div>
              </div>

              <ChatMessage
                v-for="message in messages"
                :key="message.id"
                :message="message"
                @retry="handleRetryMessage"
                @delete="handleDeleteMessage"
              />

              <ChatMessage
                v-if="streaming && streamingContent"
                :message="{
                  id: -1,
                  session_id: sessionStore.currentSession.id,
                  role: 'assistant',
                  content: streamingContent,
                  created_at: new Date().toISOString(),
                }"
                :is-streaming="true"
              />

              <div v-if="loading && !streaming" class="flex justify-start">
                <div class="glass-card max-w-[76%] rounded-[24px] rounded-bl-md px-4 py-4">
                  <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent-primary)]">ARTA</div>
                  <div class="streaming-bar mb-3 w-52" />
                  <div class="text-xs text-[var(--text-muted)]">Synthesizing the current request...</div>
                </div>
              </div>

              <div v-if="planGenerating" class="flex justify-start">
                <div class="glass-card max-w-[76%] rounded-[24px] rounded-bl-md px-4 py-4">
                  <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent-secondary)]">Planner</div>
                  <div class="streaming-bar mb-3 w-52" />
                  <div class="text-xs text-[var(--text-muted)]">Drafting queries, criteria, and execution strategy...</div>
                </div>
              </div>
            </div>

            <div class="border-t border-white/8 px-5 py-5">
              <ChatInput
                :disabled="inputDisabled"
                :placeholder="inputPlaceholder"
                @send="handleSend"
              />
            </div>
          </div>
        </GlassCard>

        <div class="space-y-4">
          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Live ops</p>
                  <h3 class="surface-panel__title">Workflow monitor</h3>
                </div>
              </div>
            </template>

            <div v-if="workflowFeed.length" class="space-y-3">
              <div
                v-for="item in workflowFeed"
                :key="item.id"
                class="callout"
                :class="{
                  'callout--accent': item.tone === 'accent',
                  'callout--success': item.tone === 'success',
                  'callout--warm': item.tone === 'warning',
                  'border border-[var(--error)]/25 bg-[var(--error)]/10': item.tone === 'error',
                }"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-[var(--text-primary)]">{{ item.title }}</div>
                    <div class="mt-1 text-sm text-[var(--text-secondary)]">{{ item.detail }}</div>
                  </div>
                  <div class="text-[11px] text-[var(--text-muted)]">
                    {{ item.updatedAt }}
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="callout">
              <div class="text-sm font-semibold text-[var(--text-primary)]">No live workflow events yet</div>
              <div class="mt-1 text-sm text-[var(--text-secondary)]">
                Search, snowball, analysis, and report progress will stream into this panel as soon as the session starts moving.
              </div>
            </div>
          </GlassCard>

          <GlassCard v-if="currentSnowballRun">
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Snowball</p>
                  <h3 class="surface-panel__title">Review and control</h3>
                </div>
                <span class="capsule">{{ currentSnowballRun.status }}</span>
              </div>
            </template>

            <div class="space-y-4">
              <div class="callout">
                <div class="text-sm font-semibold text-[var(--text-primary)]">
                  {{ currentSnowballRun.proposal_summary.topic || sessionStore.currentSession?.title || 'Current topic' }}
                </div>
                <div class="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                  <span class="capsule">Budget {{ currentSnowballRun.proposal_summary.estimated_candidate_budget ?? 0 }}</span>
                  <span class="capsule">Verified {{ currentSnowballRun.stats.verified_count ?? 0 }}</span>
                  <span class="capsule">High-confidence {{ currentSnowballRun.stats.high_confidence_count ?? 0 }}</span>
                </div>
              </div>

              <div v-if="currentSnowballRun.proposal_summary.seed_papers?.length" class="space-y-2">
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Seed papers</div>
                <div
                  v-for="seed in currentSnowballRun.proposal_summary.seed_papers.slice(0, 4)"
                  :key="seed.paper_id"
                  class="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-3"
                >
                  <div class="text-sm font-semibold text-[var(--text-primary)] line-clamp-2">{{ seed.title }}</div>
                  <div class="mt-1 text-xs text-[var(--text-muted)]">{{ seed.year ?? 'Unknown year' }} | {{ seed.citation_count }} cites</div>
                </div>
              </div>

              <div
                v-if="currentSnowballRun.status === 'awaiting_review' && snowballPreview.length"
                class="space-y-2"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Pending candidates</div>
                  <span class="capsule">Selected {{ selectedSnowballCount }}</span>
                </div>

                <div
                  v-for="candidate in snowballPreview"
                  :key="candidate.id"
                  class="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-3"
                >
                  <label class="flex items-start gap-3">
                    <input
                      type="checkbox"
                      class="mt-1 accent-[var(--accent-primary)]"
                      :checked="selectedSnowballIds.has(candidate.id)"
                      @change="toggleSnowballCandidate(candidate.id)"
                    />
                    <div class="min-w-0">
                      <div class="text-sm font-semibold text-[var(--text-primary)] line-clamp-2">{{ candidate.title }}</div>
                      <div class="mt-1 text-xs text-[var(--text-muted)]">
                        {{ candidate.direction }} | {{ candidate.year ?? 'n/a' }} | {{ candidate.citation_count }} cites | score {{ (candidate.relevance_score ?? 0).toFixed(2) }}
                      </div>
                      <div class="mt-1 text-xs text-[var(--text-secondary)]">{{ candidate.relevance_reason }}</div>
                    </div>
                  </label>
                </div>
              </div>

              <div class="flex flex-wrap gap-2">
                <button
                  v-if="currentSnowballRun.status === 'proposed'"
                  class="glass-btn"
                  :disabled="Boolean(snowballBusyAction)"
                  @click="handleSnowballAction('prepare_review')"
                >
                  {{ snowballBusyAction === 'prepare_review' ? 'Preparing...' : 'Review first' }}
                </button>
                <button
                  v-if="['proposed', 'awaiting_review'].includes(currentSnowballRun.status)"
                  class="glass-btn glass-btn-primary"
                  :disabled="Boolean(snowballBusyAction)"
                  @click="handleSnowballAction('approve_high_confidence')"
                >
                  {{ snowballBusyAction === 'approve_high_confidence' ? 'Importing...' : 'Import high-confidence' }}
                </button>
                <button
                  v-if="['proposed', 'awaiting_review'].includes(currentSnowballRun.status)"
                  class="glass-btn"
                  :disabled="Boolean(snowballBusyAction)"
                  @click="handleSnowballAction('approve_all')"
                >
                  {{ snowballBusyAction === 'approve_all' ? 'Importing...' : 'Import all' }}
                </button>
                <button
                  v-if="currentSnowballRun.status === 'awaiting_review'"
                  class="glass-btn"
                  :disabled="Boolean(snowballBusyAction) || selectedSnowballCount === 0"
                  @click="handleSnowballAction('approve_selected')"
                >
                  Import selected
                </button>
                <button
                  v-if="currentSnowballRun.status === 'awaiting_review'"
                  class="glass-btn"
                  :disabled="Boolean(snowballBusyAction) || selectedSnowballCount === 0"
                  @click="handleSnowballAction('reject_selected')"
                >
                  Reject selected
                </button>
                <button
                  v-if="['proposed', 'awaiting_review'].includes(currentSnowballRun.status)"
                  class="glass-btn"
                  :disabled="Boolean(snowballBusyAction)"
                  @click="handleSnowballAction('reject')"
                >
                  Skip snowball
                </button>
              </div>
            </div>
          </GlassCard>

          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Workflow</p>
                  <h3 class="surface-panel__title">Three-step narrative</h3>
                </div>
              </div>
            </template>

            <div class="space-y-4">
              <div
                v-for="(step, index) in workflowSteps"
                :key="step.title"
                class="flex gap-3"
              >
                <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white/[0.06] text-sm font-semibold text-[var(--text-primary)]">
                  {{ index + 1 }}
                </div>
                <div>
                  <div class="text-sm font-semibold text-[var(--text-primary)]">{{ step.title }}</div>
                  <div class="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{{ step.copy }}</div>
                </div>
              </div>
            </div>
          </GlassCard>

          <GlassCard>
            <template #header>
              <div class="surface-panel__header !mb-0">
                <div>
                  <p class="surface-panel__eyebrow">Prompt ideas</p>
                  <h3 class="surface-panel__title">High-signal next moves</h3>
                </div>
              </div>
            </template>

            <div class="space-y-2">
              <button
                v-for="topic in suggestedTopics"
                :key="`${topic}-rail`"
                class="glass-btn w-full justify-start text-left !h-auto !py-3"
                @click="handleSuggestedPrompt(topic)"
              >
                {{ topic }}
              </button>
            </div>
          </GlassCard>
        </div>
      </div>
    </template>
  </div>
</template>
