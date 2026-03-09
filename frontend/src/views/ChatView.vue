<script setup lang="ts">
import { computed, ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import type { ChatMessage as ChatMessageType } from '@/types'
import { chatApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import { useWebSocket } from '@/composables/useWebSocket'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const sessionStore = useSessionStore()
const backendState = useBackendState()
const messages = ref<ChatMessageType[]>([])
const loading = ref(false)
const streaming = ref(false)
const streamingContent = ref('')
const scrollContainer = ref<HTMLElement | null>(null)
const planGenerating = ref(false)
const actionError = ref('')

// WebSocket connection - reactive to session changes
let ws: ReturnType<typeof useWebSocket> | null = null

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
      // Replace streaming content with final message
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
    // Add a system-like message about the plan
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
    if (streamingContent.value) {
      // Save whatever was streamed
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

  // Check if this is a plan generation command
  const planCmd = content.match(/^\/plan\s+(.+)/i)

  // Optimistic user message
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
    // Generate search plan via WebSocket
    ws.send('generate_plan', { topic: planCmd[1] })
    return
  } else if (planCmd) {
    actionError.value = 'Search plan generation requires a live backend WebSocket connection.'
    await checkBackend(true)
    return
  }

  // Send via WebSocket for streaming
  if (ws && ws.connected.value) {
    loading.value = true
    streamingContent.value = ''
    if (!ws.send('chat_send', { content })) {
      loading.value = false
      actionError.value = 'Live chat connection dropped before the message could be sent.'
      await checkBackend(true)
    }
  } else {
    // Fallback to REST
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
      <div
        v-if="actionError"
        class="mb-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]"
      >
        {{ actionError }}
      </div>
      <div
        ref="scrollContainer"
        class="flex-1 overflow-y-auto space-y-4 pr-2 pb-4"
      >
        <div
          v-if="messages.length === 0 && !loading && !streaming"
          class="flex flex-col items-center justify-center h-full text-[var(--text-muted)] gap-2"
        >
          <p>Send a message to discuss your research topic.</p>
          <p class="text-xs">Tip: Use <code class="px-1 py-0.5 rounded bg-white/5">/plan [topic]</code> to directly generate a search plan.</p>
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
        <!-- Loading indicator -->
        <div v-if="loading && !streaming" class="flex justify-start">
          <div class="glass-card rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]">
            <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span class="inline-block w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
              ARTA is thinking...
            </div>
          </div>
        </div>
        <!-- Plan generating indicator -->
        <div v-if="planGenerating" class="flex justify-start">
          <div class="glass-card rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]">
            <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span class="inline-block w-2 h-2 rounded-full bg-[var(--accent-secondary)] animate-pulse" />
              Generating search plan...
            </div>
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
