<script setup lang="ts">
import { computed } from 'vue'
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

const formattedTime = computed(() => {
  const date = new Date(props.message.created_at)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <div
    class="flex w-full fade-in"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[75%] rounded-2xl px-4 py-3"
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
