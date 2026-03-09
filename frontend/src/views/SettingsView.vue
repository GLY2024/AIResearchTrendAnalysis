<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { settingsApi } from '@/composables/useApi'
import GlassCard from '@/components/common/GlassCard.vue'
import axios from 'axios'

interface SettingField {
  key: string
  label: string
  value: string
  saved: boolean
  saving: boolean
  validating: boolean
  validationResult: { valid: boolean; message: string } | null
}

// API keys
const apiKeys = ref<SettingField[]>([
  { key: 'openai_api_key', label: 'OpenAI API Key', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'anthropic_api_key', label: 'Anthropic API Key', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'google_api_key', label: 'Google API Key', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'scopus_api_key', label: 'Scopus API Key', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'zotero_api_key', label: 'Zotero API Key', value: '', saved: false, saving: false, validating: false, validationResult: null },
])

// Model role mapping
const modelRoles = ref<SettingField[]>([
  { key: 'model_chat', label: 'Chat Model', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'model_planner', label: 'Planner Model', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'model_analyst', label: 'Analyst Model', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'model_publisher', label: 'Publisher Model', value: '', saved: false, saving: false, validating: false, validationResult: null },
  { key: 'model_executor', label: 'Executor Model', value: '', saved: false, saving: false, validating: false, validationResult: null },
])

// Keys that support validation
const validatableKeys = new Set(['openai_api_key', 'anthropic_api_key', 'google_api_key'])

async function loadSettings() {
  try {
    const settings = await settingsApi.list()
    for (const s of settings) {
      const ak = apiKeys.value.find(f => f.key === s.key)
      if (ak) { ak.value = s.value; ak.saved = true }
      const mr = modelRoles.value.find(f => f.key === s.key)
      if (mr) { mr.value = s.value; mr.saved = true }
    }
  } catch {
    // settings may not exist yet
  }
}

async function saveSetting(field: SettingField, isSensitive = false) {
  field.saving = true
  try {
    await settingsApi.update({
      key: field.key,
      value: field.value,
      is_sensitive: isSensitive,
    })
    field.saved = true
    field.validationResult = null
  } finally {
    field.saving = false
  }
}

async function validateKey(field: SettingField) {
  if (!field.value || field.value.includes('***')) return
  field.validating = true
  field.validationResult = null
  try {
    const resp = await axios.post('/api/validate-key', {
      key: field.key,
      value: field.value,
    })
    field.validationResult = resp.data
  } catch (e: unknown) {
    field.validationResult = { valid: false, message: 'Validation request failed' }
  } finally {
    field.validating = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-semibold text-[var(--text-primary)] mb-1">Settings</h1>
    <p class="text-sm text-[var(--text-secondary)] mb-6">
      Configure API keys and model assignments.
    </p>

    <!-- API Keys -->
    <GlassCard title="API Keys" class="mb-6">
      <div class="space-y-4">
        <div v-for="field in apiKeys" :key="field.key">
          <label class="block text-xs text-[var(--text-muted)] mb-1">{{ field.label }}</label>
          <div class="flex gap-2">
            <input
              v-model="field.value"
              type="password"
              class="glass-input flex-1"
              :placeholder="field.saved ? '••••••••' : 'Enter key...'"
              @input="field.saved = false; field.validationResult = null"
            />
            <button
              class="glass-btn glass-btn-primary shrink-0"
              :disabled="field.saving || !field.value"
              @click="saveSetting(field, true)"
            >
              {{ field.saving ? '...' : 'Save' }}
            </button>
            <button
              v-if="validatableKeys.has(field.key)"
              class="glass-btn shrink-0"
              :disabled="field.validating || !field.value || field.value.includes('***')"
              @click="validateKey(field)"
            >
              {{ field.validating ? '...' : 'Test' }}
            </button>
          </div>
          <!-- Validation result -->
          <div
            v-if="field.validationResult"
            class="mt-1 text-xs"
            :class="field.validationResult.valid ? 'text-[var(--success)]' : 'text-[var(--error)]'"
          >
            {{ field.validationResult.valid ? '✓' : '✗' }} {{ field.validationResult.message }}
          </div>
        </div>
      </div>
    </GlassCard>

    <!-- Model Roles -->
    <GlassCard title="Model Role Mapping">
      <p class="text-xs text-[var(--text-muted)] mb-4">
        Assign which model handles each role. Examples: gpt-4o, claude-sonnet-4-20250514, gemini/gemini-2.0-flash
      </p>
      <div class="space-y-4">
        <div v-for="field in modelRoles" :key="field.key">
          <label class="block text-xs text-[var(--text-muted)] mb-1">{{ field.label }}</label>
          <div class="flex gap-2">
            <input
              v-model="field.value"
              type="text"
              class="glass-input flex-1"
              placeholder="e.g. gpt-4o"
              @input="field.saved = false"
            />
            <button
              class="glass-btn glass-btn-primary shrink-0"
              :disabled="field.saving || !field.value"
              @click="saveSetting(field)"
            >
              {{ field.saving ? '...' : 'Save' }}
            </button>
          </div>
        </div>
      </div>
    </GlassCard>
  </div>
</template>
