<script setup lang="ts">
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { registerECharts, chartTheme } from '@/composables/useChartSetup'
import GlassModal from './GlassModal.vue'

registerECharts()

const props = withDefaults(
  defineProps<{
    option: Record<string, unknown>
    title?: string
    height?: string
    allowFullscreen?: boolean
  }>(),
  {
    title: '',
    height: '400px',
    allowFullscreen: true,
  }
)

const showFullscreen = ref(false)

const themedOption = computed(() => {
  const opt = chartTheme(props.option)
  // Enable dataZoom for complex chart types
  const series = opt.series as Array<{ type?: string }> | undefined
  if (series?.some(s => s.type === 'graph' || s.type === 'scatter')) {
    if (!opt.dataZoom) {
      opt.dataZoom = [
        { type: 'inside', zoomOnMouseWheel: true },
      ]
    }
  }
  return opt
})
</script>

<template>
  <div class="chart-container glass-card p-4">
    <!-- Title bar -->
    <div v-if="title || allowFullscreen" class="flex items-center justify-between mb-3">
      <h4 v-if="title" class="text-sm font-medium text-[var(--text-primary)]">{{ title }}</h4>
      <button
        v-if="allowFullscreen"
        class="glass-btn !p-1.5 !rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        title="Fullscreen"
        @click="showFullscreen = true"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" />
        </svg>
      </button>
    </div>

    <!-- Chart -->
    <VChart
      :option="themedOption"
      class="w-full"
      :style="{ height }"
      autoresize
      @click="allowFullscreen && (showFullscreen = true)"
    />

    <!-- Fullscreen modal -->
    <GlassModal
      :visible="showFullscreen"
      :title="title || 'Chart'"
      width="90vw"
      @close="showFullscreen = false"
    >
      <VChart
        :option="themedOption"
        style="width: 100%; height: 75vh"
        autoresize
      />
    </GlassModal>
  </div>
</template>

<style scoped>
.chart-container {
  cursor: default;
}
</style>
