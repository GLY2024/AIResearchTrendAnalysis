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

const emit = defineEmits<{
  retry: [message: ChatMessage]
  delete: [message: ChatMessage]
}>()

const isUser = computed(() => props.message.role === 'user')
const isSystem = computed(() => props.message.role === 'system')
const metadata = computed(() => props.message.metadata ?? {})
const isFailed = computed(() => metadata.value.status === 'failed')
const retryable = computed(() => metadata.value.retryable !== false)
const errorLabel = computed(() => {
  const code = metadata.value.error_code
  const statusCode = metadata.value.status_code
  if (typeof statusCode === 'number' && code) return `${String(code)} / HTTP ${statusCode}`
  if (typeof statusCode === 'number') return `HTTP ${statusCode}`
  if (code) return String(code)
  return ''
})
const errorDetail = computed(() => {
  const detail = metadata.value.error_detail
  return typeof detail === 'string' ? detail : ''
})
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

function retryMessage() {
  emit('retry', props.message)
}

function deleteMessage() {
  emit('delete', props.message)
}
</script>

<template>
  <div
    class="flex w-full fade-in group"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      v-if="isSystem"
      class="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-[var(--text-secondary)]"
    >
      <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--accent-secondary)]">
        Workflow
      </div>
      <div class="leading-7 whitespace-pre-wrap">
        {{ message.content }}
      </div>
      <div class="mt-1.5 text-[10px] text-[var(--text-muted)]">
        {{ formattedTime }}
      </div>
    </div>

    <div
      v-else
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
      <div
        v-if="!isUser && !isStreaming"
        class="absolute right-2 top-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      >
        <button
          v-if="isFailed && retryable"
          class="glass-btn !min-h-0 !rounded-md !px-2.5 !py-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          title="Retry"
          @click="retryMessage"
        >
          Retry
        </button>
        <button
          v-if="isFailed"
          class="glass-btn !min-h-0 !rounded-md !px-2.5 !py-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          title="Delete"
          @click="deleteMessage"
        >
          Delete
        </button>
        <button
          class="glass-btn !p-1 !rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)]"
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
      </div>

      <!-- Message content -->
      <div v-if="isUser" class="text-sm leading-relaxed whitespace-pre-wrap">
        {{ message.content }}
      </div>
      <StreamingText
        v-else
        :text="message.content"
        :is-streaming="isStreaming"
      />

      <div
        v-if="isFailed"
        class="mt-3 rounded-2xl border border-[var(--error)]/25 bg-[var(--error)]/10 px-3 py-2 text-xs text-[var(--error)]"
      >
        <div class="font-semibold">
          Request failed<span v-if="errorLabel">: {{ errorLabel }}</span>
        </div>
        <div v-if="errorDetail" class="mt-1 leading-6 text-[var(--text-secondary)]">
          {{ errorDetail }}
        </div>
      </div>

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
