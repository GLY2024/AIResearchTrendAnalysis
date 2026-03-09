<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    placeholder: 'Type a message...',
  }
)

const emit = defineEmits<{
  send: [content: string]
}>()

const content = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function autoResize() {
  const textarea = textareaRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
}

watch(content, () => {
  nextTick(autoResize)
})

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function handleSend() {
  const trimmed = content.value.trim()
  if (!trimmed || props.disabled) return
  emit('send', trimmed)
  content.value = ''
  nextTick(autoResize)
}
</script>

<template>
  <div class="glass-card flex items-end gap-2 p-3">
    <textarea
      ref="textareaRef"
      v-model="content"
      :placeholder="placeholder"
      :disabled="disabled"
      rows="1"
      class="glass-input flex-1 resize-none overflow-y-auto leading-normal"
      style="max-height: 200px"
      @keydown="handleKeydown"
    />
    <button
      class="glass-btn glass-btn-primary shrink-0 flex items-center justify-center h-10 w-10 rounded-xl p-0"
      :disabled="disabled || !content.trim()"
      :class="{ 'opacity-40 cursor-not-allowed': disabled || !content.trim() }"
      @click="handleSend"
    >
      <!-- Send arrow icon -->
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        class="w-5 h-5"
      >
        <path
          d="M3.105 3.29a.75.75 0 0 1 .814-.12l13.5 6.75a.75.75 0 0 1 0 1.34l-13.5 6.75a.75.75 0 0 1-1.064-.85L4.64 11H10a.75.75 0 0 0 0-1.5H4.64L2.855 3.46a.75.75 0 0 1 .25-.17Z"
        />
      </svg>
    </button>
  </div>
</template>
