<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  padding?: boolean
}>(), {
  padding: true,
})
</script>

<template>
  <div class="glass-card" :class="{ 'p-5': padding }">
    <div v-if="$slots.header || title" class="mb-4">
      <slot name="header">
        <h3 class="text-base font-semibold text-[var(--text-primary)]">{{ title }}</h3>
      </slot>
    </div>

    <div>
      <slot />
    </div>

    <div v-if="$slots.footer" class="mt-4 pt-3 border-t border-white/10">
      <slot name="footer" />
    </div>
  </div>
</template>
