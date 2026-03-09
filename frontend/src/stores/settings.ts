import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AppSetting } from '@/types'
import { settingsApi } from '@/composables/useApi'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSetting[]>([])
  const loading = ref(false)

  async function fetchSettings() {
    loading.value = true
    try {
      settings.value = await settingsApi.list()
    } finally {
      loading.value = false
    }
  }

  async function updateSetting(key: string, value: string, isSensitive = false) {
    const result = await settingsApi.update({ key, value, is_sensitive: isSensitive })
    const idx = settings.value.findIndex(s => s.key === key)
    if (idx >= 0) {
      settings.value[idx] = result
    } else {
      settings.value.push(result)
    }
  }

  async function deleteSetting(key: string) {
    await settingsApi.delete(key)
    settings.value = settings.value.filter(s => s.key !== key)
  }

  function getSetting(key: string): string {
    return settings.value.find(s => s.key === key)?.value ?? ''
  }

  return { settings, loading, fetchSettings, updateSetting, deleteSetting, getSetting }
})
