<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = withDefaults(
  defineProps<{
    text: string
    isStreaming?: boolean
  }>(),
  {
    isStreaming: false,
  }
)

// Custom renderer for glass theme classes
const renderer = new marked.Renderer()
renderer.heading = ({ text, depth }) => {
  return `<h${depth} class="md-heading md-h${depth}">${text}</h${depth}>`
}
renderer.link = ({ href, text }) => {
  return `<a href="${href}" class="md-link" target="_blank" rel="noopener">${text}</a>`
}
renderer.table = (token) => {
  let headerHtml = ''
  for (const cell of token.header) {
    headerHtml += `<th${cell.align ? ` style="text-align:${cell.align}"` : ''}>${cell.text}</th>`
  }
  let bodyHtml = ''
  for (const row of token.rows) {
    let rowHtml = ''
    for (const cell of row) {
      rowHtml += `<td${cell.align ? ` style="text-align:${cell.align}"` : ''}>${cell.text}</td>`
    }
    bodyHtml += `<tr>${rowHtml}</tr>`
  }
  return `<table class="md-table"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`
}
renderer.blockquote = ({ text }) => {
  return `<blockquote class="md-blockquote">${text}</blockquote>`
}
renderer.code = ({ text, lang }) => {
  return `<pre class="code-block"><code class="language-${lang || ''}">${text}</code></pre>`
}
renderer.codespan = ({ text }) => {
  return `<code class="inline-code">${text}</code>`
}
renderer.hr = () => {
  return `<hr class="md-hr" />`
}

marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
})

const renderedHtml = computed(() => {
  if (!props.text) return ''
  return marked.parse(props.text) as string
})
</script>

<template>
  <div class="streaming-text md-content text-sm leading-relaxed">
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
