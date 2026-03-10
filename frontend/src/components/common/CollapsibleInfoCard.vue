<script setup lang="ts">
import { ref } from 'vue'
import GlassCard from './GlassCard.vue'

const props = withDefaults(
  defineProps<{
    eyebrow: string
    title: string
    defaultOpen?: boolean
  }>(),
  {
    defaultOpen: false,
  },
)

const open = ref(props.defaultOpen)
</script>

<template>
  <GlassCard>
    <template #header>
      <button
        class="flex w-full items-center justify-between gap-3 text-left"
        @click="open = !open"
      >
        <div>
          <p class="surface-panel__eyebrow">{{ eyebrow }}</p>
          <h3 class="surface-panel__title">{{ title }}</h3>
        </div>

        <div class="flex items-center gap-3">
          <span class="capsule">{{ open ? 'Expanded' : 'Collapsed' }}</span>
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            class="shrink-0 text-[var(--text-muted)] transition-transform"
            :class="open ? 'rotate-180' : ''"
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </div>
      </button>
    </template>

    <div v-if="open">
      <slot />
    </div>
  </GlassCard>
</template>
