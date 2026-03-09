<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'default' | 'primary'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>(), {
  variant: 'default',
  size: 'md',
  loading: false,
  disabled: false,
})
</script>

<template>
  <button
    :class="[
      variant === 'primary' ? 'glass-btn glass-btn-primary' : 'glass-btn',
      {
        'text-xs px-2.5 py-1': size === 'sm',
        'text-sm px-4 py-2': size === 'md',
        'text-base px-6 py-2.5': size === 'lg',
        'opacity-50 cursor-not-allowed': disabled || loading,
      },
    ]"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="inline-flex items-center gap-2">
      <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <slot />
    </span>
    <slot v-else />
  </button>
</template>
