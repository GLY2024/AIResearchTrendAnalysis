<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatMessage } from '@/types'
import StreamingText from './StreamingText.vue'

const props = withDefaults(
  defineProps<{
    message: ChatMessage
    isStreaming?: boolean
  }>(),
  { isStreaming: false }
)

const isUser = computed(() => props.message.role === 'user')
const showCopied = ref(false)

const formattedTime = computed(() => {
  const date = new Date(props.message.created_at)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    showCopied.value = true
    setTimeout(() => { showCopied.value = false }, 1500)
  } catch { /* ignore */ }
}
</script>

<template>
  <div
    class="flex w-full fade-in group"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[75%] rounded-2xl px-4 py-3 relative"
      :class="
        isUser
          ? 'bg-[var(--accent-primary)] text-white rounded-br-sm'
          : 'glass-card rounded-bl-sm'
      "
    >
      <!-- Role label for assistant -->
      <div
        v-if="!isUser"
        class="text-xs font-semibold mb-1"
        style="color: var(--accent-secondary)"
      >
        ARTA
      </div>

      <!-- Copy button (assistant messages) -->
      <button
        v-if="!isUser && !isStreaming"
        class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity glass-btn !p-1 !rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        title="Copy"
        @click="copyContent"
      >
        <svg v-if="!showCopied" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <rect x="5" y="5" width="9" height="9" rx="1.5" />
          <path d="M5 11H3.5A1.5 1.5 0 0 1 2 9.5v-7A1.5 1.5 0 0 1 3.5 1h7A1.5 1.5 0 0 1 12 2.5V5" />
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round">
          <path d="M3 8.5l3 3 7-7" />
        </svg>
      </button>

      <!-- Message content -->
      <div v-if="isUser" class="text-sm leading-relaxed whitespace-pre-wrap">
        {{ message.content }}
      </div>
      <StreamingText
        v-else
        :text="message.content"
        :is-streaming="isStreaming"
      />

      <!-- Timestamp -->
      <div
        class="text-[10px] mt-1.5 select-none"
        :class="isUser ? 'text-white/60 text-right' : 'text-[var(--text-muted)]'"
      >
        {{ formattedTime }}
      </div>
    </div>
  </div>
</template>
