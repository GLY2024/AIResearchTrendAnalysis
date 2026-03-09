<script setup lang="ts">
withDefaults(defineProps<{
  visible: boolean
  title: string
  width?: string
}>(), {
  width: '500px',
})

const emit = defineEmits<{
  close: []
}>()

function onOverlayClick(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @click="onOverlayClick"
      >
        <!-- Overlay -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" />

        <!-- Dialog -->
        <div
          class="glass-card relative z-10 p-6 fade-in"
          :style="{ width, maxWidth: '90vw', maxHeight: '85vh' }"
        >
          <!-- Header -->
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">{{ title }}</h2>
            <button
              class="glass-btn w-8 h-8 flex items-center justify-center !p-0 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              @click="emit('close')"
              aria-label="Close"
            >
              &times;
            </button>
          </div>

          <!-- Body -->
          <div class="overflow-y-auto" style="max-height: calc(85vh - 120px)">
            <slot />
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer" class="mt-4 pt-3 border-t border-white/10">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--transition-normal);
}
.modal-enter-active .glass-card,
.modal-leave-active .glass-card {
  transition: transform var(--transition-normal), opacity var(--transition-normal);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .glass-card {
  transform: translateY(16px) scale(0.96);
  opacity: 0;
}
.modal-leave-to .glass-card {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
