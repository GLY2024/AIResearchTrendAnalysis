<script setup lang="ts">
import { computed, ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ChatMessage as ChatMessageType } from '@/types'
import { chatApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { useWebSocket } from '@/composables/useWebSocket'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

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

// WebSocket connection - reactive to session changes
let ws: ReturnType<typeof useWebSocket> | null = null

const suggestedTopics = [
  'What are the latest trends in large language models?',
  'Help me understand transformer architectures',
  'Summarize key papers on federated learning',
]

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
    const msg = data.message as ChatMessageType
    if (msg) {
      messages.value.push(msg)
    }
    streaming.value = false
    streamingContent.value = ''
    nextTick(scrollToBottom)
  })

  ws.on('plan_generating', () => {
    planGenerating.value = true
  })

  ws.on('plan_generated', (data: Record<string, unknown>) => {
    planGenerating.value = false
    messages.value.push({
      id: Date.now(),
      session_id: sessionStore.currentSession!.id,
      role: 'assistant',
      content: `**Search plan generated!** Topic: "${(data.plan_data as Record<string, string>)?.topic ?? 'Unknown'}"\n\nGo to the **Search Plan** page to review and approve it.`,
      created_at: new Date().toISOString(),
    })
    nextTick(scrollToBottom)
  })

  ws.on('error', (data: Record<string, unknown>) => {
    loading.value = false
    streaming.value = false
    planGenerating.value = false

    if (data.error_code === 'no_api_key') {
      needsApiKey.value = true
      actionError.value = (data.message as string) || 'API key not configured.'
      return
    }

    if (streamingContent.value) {
      messages.value.push({
        id: Date.now(),
        session_id: sessionStore.currentSession!.id,
        role: 'assistant',
        content: streamingContent.value || (data.message as string) || 'An error occurred.',
        created_at: new Date().toISOString(),
      })
      streamingContent.value = ''
    }
  })
}

async function loadMessages() {
  if (!sessionStore.currentSession) return
  actionError.value = ''
  try {
    messages.value = await chatApi.getMessages(sessionStore.currentSession.id)
    await nextTick()
    scrollToBottom()
    setupWebSocket()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to load chat history.'
    await checkBackend(true)
  }
}

function scrollToBottom() {
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

async function handleSend(content: string) {
  console.log('[ARTA:Chat] handleSend called, session:', sessionStore.currentSession?.id, 'ws connected:', ws?.connected.value)
  actionError.value = ''
  if (!sessionStore.currentSession) {
    console.warn('[ARTA:Chat] No session selected, ignoring send')
    actionError.value = 'Select or create a session before sending messages.'
    return
  }

  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('chat')
    return
  }

  const planCmd = content.match(/^\/plan\s+(.+)/i)

  const userMsg: ChatMessageType = {
    id: Date.now(),
    session_id: sessionStore.currentSession.id,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  }
  messages.value.push(userMsg)
  await nextTick()
  scrollToBottom()

  if (planCmd && ws?.connected.value) {
    ws.send('generate_plan', { topic: planCmd[1] })
    return
  } else if (planCmd) {
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
  } else {
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
        id: Date.now() + 1,
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

const inputDisabled = computed(() => {
  return loading.value || streaming.value || backendState.status !== 'online'
})

const inputPlaceholder = computed(() => {
  if (backendState.status !== 'online') {
    return 'Backend offline. Start the backend to send messages.'
  }
  return 'Type a message...'
})

watch(() => sessionStore.currentSessionId, loadMessages)
onMounted(loadMessages)
onUnmounted(() => {
  if (ws) ws.disconnect()
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="mb-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-[var(--text-primary)]">Chat</h1>
        <p class="text-sm text-[var(--text-secondary)]">
          {{ sessionStore.currentSession?.title ?? 'No session selected' }}
        </p>
      </div>
      <button
        v-if="sessionStore.currentSession"
        class="glass-btn glass-btn-primary text-sm"
        :disabled="planGenerating"
        @click="handleGeneratePlan"
      >
        {{ planGenerating ? 'Generating...' : 'Generate Search Plan' }}
      </button>
    </div>

    <!-- No session state -->
    <div
      v-if="!sessionStore.currentSession"
      class="flex-1 flex items-center justify-center text-[var(--text-muted)]"
    >
      Create or select a session to start chatting.
    </div>

    <!-- Chat area -->
    <template v-else>
      <!-- API key missing - step guide card -->
      <div
        v-if="needsApiKey"
        class="mb-4 glass-card p-6"
      >
        <h3 class="text-base font-semibold text-[var(--text-primary)] mb-4">Get Started with ARTA</h3>
        <div class="space-y-3">
          <div class="flex items-start gap-3">
            <span class="flex items-center justify-center w-6 h-6 rounded-full bg-[var(--accent-primary)] text-white text-xs font-bold shrink-0">1</span>
            <div>
              <p class="text-sm font-medium text-[var(--text-primary)]">Configure an API Key</p>
              <p class="text-xs text-[var(--text-muted)]">Add your OpenAI, Anthropic, or OpenRouter key in Settings.</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <span class="flex items-center justify-center w-6 h-6 rounded-full bg-[var(--glass-border)] text-[var(--text-muted)] text-xs font-bold shrink-0">2</span>
            <div>
              <p class="text-sm font-medium text-[var(--text-secondary)]">Select Models</p>
              <p class="text-xs text-[var(--text-muted)]">Choose which model to use for each role (chat, planner, etc.).</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <span class="flex items-center justify-center w-6 h-6 rounded-full bg-[var(--glass-border)] text-[var(--text-muted)] text-xs font-bold shrink-0">3</span>
            <div>
              <p class="text-sm font-medium text-[var(--text-secondary)]">Start Researching</p>
              <p class="text-xs text-[var(--text-muted)]">Chat about your topic, generate search plans, and analyze papers.</p>
            </div>
          </div>
        </div>
        <button
          class="glass-btn glass-btn-primary text-sm mt-4"
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
      <div
        ref="scrollContainer"
        class="flex-1 overflow-y-auto space-y-4 pr-2 pb-4"
      >
        <!-- Empty state welcome card -->
        <div
          v-if="messages.length === 0 && !loading && !streaming"
          class="flex flex-col items-center justify-center h-full"
        >
          <div class="glass-card p-8 max-w-md text-center">
            <div class="w-14 h-14 rounded-2xl bg-[var(--accent-primary)]/20 flex items-center justify-center mx-auto mb-4">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="1.5" stroke-linecap="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-2">Welcome to ARTA Chat</h2>
            <p class="text-sm text-[var(--text-secondary)] mb-5">
              Discuss your research topic, ask questions, or generate a search plan.
            </p>
            <!-- Suggested topics -->
            <div class="space-y-2">
              <button
                v-for="topic in suggestedTopics"
                :key="topic"
                class="w-full text-left glass-btn text-xs py-2.5 px-4"
                @click="handleSend(topic)"
              >
                {{ topic }}
              </button>
            </div>
            <div class="mt-4 pt-3 border-t border-white/10">
              <p class="text-xs text-[var(--text-muted)]">
                Use <code class="px-1 py-0.5 rounded bg-white/5 text-[var(--accent-primary)]">/plan [topic]</code> to generate a search plan directly.
              </p>
            </div>
          </div>
        </div>
        <ChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
        />
        <!-- Streaming message -->
        <ChatMessage
          v-if="streaming && streamingContent"
          :message="{
            id: -1,
            session_id: sessionStore.currentSession!.id,
            role: 'assistant',
            content: streamingContent,
            created_at: new Date().toISOString(),
          }"
          :is-streaming="true"
        />
        <!-- Loading indicator - gradient pulse bar -->
        <div v-if="loading && !streaming" class="flex justify-start">
          <div class="glass-card rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]">
            <div class="text-xs font-semibold mb-1.5" style="color: var(--accent-secondary)">ARTA</div>
            <div class="streaming-bar w-48 mb-2" />
            <div class="text-xs text-[var(--text-muted)]">Thinking...</div>
          </div>
        </div>
        <!-- Plan generating indicator -->
        <div v-if="planGenerating" class="flex justify-start">
          <div class="glass-card rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]">
            <div class="text-xs font-semibold mb-1.5" style="color: var(--accent-secondary)">ARTA</div>
            <div class="streaming-bar w-48 mb-2" />
            <div class="text-xs text-[var(--text-muted)]">Generating search plan...</div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="mt-2">
        <ChatInput
          :disabled="inputDisabled"
          :placeholder="inputPlaceholder"
          @send="handleSend"
        />
      </div>
    </template>
  </div>
</template>
