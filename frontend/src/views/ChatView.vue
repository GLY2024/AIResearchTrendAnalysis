<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import type { ChatMessage as ChatMessageType } from '@/types'
import { chatApi } from '@/composables/useApi'
import { useSessionStore } from '@/stores/session'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const sessionStore = useSessionStore()
const messages = ref<ChatMessageType[]>([])
const loading = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)

async function loadMessages() {
  if (!sessionStore.currentSession) return
  messages.value = await chatApi.getMessages(sessionStore.currentSession.id)
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

async function handleSend(content: string) {
  if (!sessionStore.currentSession) return

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

  loading.value = true
  try {
    const reply = await chatApi.send({
      session_id: sessionStore.currentSession.id,
      content,
    })
    messages.value.push(reply)
  } catch {
    messages.value.push({
      id: Date.now() + 1,
      session_id: sessionStore.currentSession.id,
      role: 'assistant',
      content: 'Sorry, something went wrong. Please try again.',
      created_at: new Date().toISOString(),
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

watch(() => sessionStore.currentSessionId, loadMessages)
onMounted(loadMessages)
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="mb-4">
      <h1 class="text-xl font-semibold text-[var(--text-primary)]">Chat</h1>
      <p class="text-sm text-[var(--text-secondary)]">
        {{ sessionStore.currentSession?.title ?? 'No session selected' }}
      </p>
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
        ref="scrollContainer"
        class="flex-1 overflow-y-auto space-y-4 pr-2 pb-4"
      >
        <div
          v-if="messages.length === 0 && !loading"
          class="flex items-center justify-center h-full text-[var(--text-muted)]"
        >
          Send a message to begin your research.
        </div>
        <ChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
        />
        <!-- Loading indicator -->
        <div v-if="loading" class="flex justify-start">
          <div class="glass-card rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]">
            <div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span class="inline-block w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
              ARTA is thinking...
            </div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="mt-2">
        <ChatInput @send="handleSend" />
      </div>
    </template>
  </div>
</template>
