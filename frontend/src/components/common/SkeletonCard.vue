<script setup lang="ts">
withDefaults(
  defineProps<{
    height?: string
    lines?: number
  }>(),
  {
    height: '120px',
    lines: 3,
  }
)
</script>

<template>
  <div class="skeleton-card glass-card p-5" :style="{ minHeight: height }">
    <div class="skeleton-line w-1/3 h-4 mb-4 rounded" />
    <div
      v-for="i in lines"
      :key="i"
      class="skeleton-line h-3 rounded mb-2.5"
      :style="{ width: i === lines ? '60%' : '100%' }"
    />
  </div>
</template>

<style scoped>
.skeleton-line {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.06) 25%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.06) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
