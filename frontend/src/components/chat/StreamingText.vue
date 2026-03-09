<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    text: string
    isStreaming?: boolean
  }>(),
  {
    isStreaming: false,
  }
)

/**
 * Basic markdown-like rendering:
 * - **bold** -> <strong>
 * - `inline code` -> <code>
 * - ```code blocks``` -> <pre><code>
 */
const renderedHtml = computed(() => {
  let html = escapeHtml(props.text)

  // Fenced code blocks: ```...```
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_match, _lang, code) =>
      `<pre class="code-block"><code>${code.trim()}</code></pre>`
  )

  // Inline code: `...`
  html = html.replace(
    /`([^`\n]+)`/g,
    '<code class="inline-code">$1</code>'
  )

  // Bold: **...**
  html = html.replace(
    /\*\*([^*]+)\*\*/g,
    '<strong>$1</strong>'
  )

  // Convert newlines to <br> (outside of pre blocks)
  html = html.replace(/\n/g, '<br>')

  return html
})

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return text.replace(/[&<>"']/g, (c) => map[c] ?? c)
}
</script>

<template>
  <div class="streaming-text text-sm leading-relaxed">
    <span v-html="renderedHtml" />
    <span
      v-if="isStreaming"
      class="streaming-cursor"
      aria-hidden="true"
    />
  </div>
</template>

<style scoped>
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: var(--accent-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.streaming-text :deep(.code-block) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  margin: 8px 0;
  overflow-x: auto;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
}

.streaming-text :deep(.inline-code) {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 0.9em;
}

.streaming-text :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}
</style>
