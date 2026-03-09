<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { settingsApi } from '@/composables/useApi'
import axios from 'axios'

// --- Types ---
interface Provider {
  id: string
  name: string
  description: string
  icon: string
  fields: {
    apiKey: string
    baseUrl: string
  }
  defaults: {
    baseUrl: string
  }
}

interface ProviderState {
  apiKey: string
  baseUrl: string
  enabled: boolean
  testing: boolean
  testResult: { ok: boolean; message: string } | null
  saving: boolean
  dirty: boolean
}

interface ModelRole {
  key: string
  label: string
  description: string
  value: string
  saving: boolean
  dirty: boolean
}

// --- Provider definitions ---
const providers: Provider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4o-mini and compatible APIs (vLLM, LM Studio, etc.)',
    icon: '🟢',
    fields: { apiKey: 'openai_api_key', baseUrl: 'openai_base_url' },
    defaults: { baseUrl: 'https://api.openai.com/v1' },
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude Opus, Sonnet, Haiku and compatible APIs',
    icon: '🟠',
    fields: { apiKey: 'anthropic_api_key', baseUrl: 'anthropic_base_url' },
    defaults: { baseUrl: 'https://api.anthropic.com' },
  },
]

// --- State ---
const providerStates = reactive<Record<string, ProviderState>>({})
for (const p of providers) {
  providerStates[p.id] = {
    apiKey: '',
    baseUrl: p.defaults.baseUrl,
    enabled: false,
    testing: false,
    testResult: null,
    saving: false,
    dirty: false,
  }
}

const modelRoles = ref<ModelRole[]>([
  { key: 'model_chat', label: 'Chat', description: 'General conversation and research discussion', value: '', saving: false, dirty: false },
  { key: 'model_planner', label: 'Planner', description: 'Search strategy and plan generation', value: '', saving: false, dirty: false },
  { key: 'model_analyst', label: 'Analyst', description: 'Data analysis and interpretation', value: '', saving: false, dirty: false },
  { key: 'model_publisher', label: 'Publisher', description: 'Report writing and formatting', value: '', saving: false, dirty: false },
  { key: 'model_executor', label: 'Executor', description: 'Search execution and tool calling', value: '', saving: false, dirty: false },
])

const extraKeys = ref<{ key: string; label: string; value: string; saving: boolean; dirty: boolean }[]>([
  { key: 'scopus_api_key', label: 'Scopus API Key', value: '', saving: false, dirty: false },
])

const loaded = ref(false)

// --- Load settings from backend ---
async function loadSettings() {
  try {
    const settings = await settingsApi.list()
    const map = new Map(settings.map((s: { key: string; value: string }) => [s.key, s.value]))

    for (const p of providers) {
      const state = providerStates[p.id]
      const key = map.get(p.fields.apiKey)
      const url = map.get(p.fields.baseUrl)
      if (key) { state.apiKey = key; state.enabled = true }
      if (url) state.baseUrl = url
    }

    for (const role of modelRoles.value) {
      const v = map.get(role.key)
      if (v) role.value = v
    }

    for (const ek of extraKeys.value) {
      const v = map.get(ek.key)
      if (v) ek.value = v
    }
  } catch (err) {
    console.error('[ARTA:Settings] Failed to load settings:', err)
  }
  loaded.value = true
}

// --- Save provider ---
async function saveProvider(providerId: string) {
  const p = providers.find(x => x.id === providerId)!
  const state = providerStates[providerId]
  state.saving = true
  try {
    // Save API key
    if (state.apiKey && !state.apiKey.includes('***')) {
      await settingsApi.update({ key: p.fields.apiKey, value: state.apiKey, is_sensitive: true })
    }
    // Save base URL
    await settingsApi.update({ key: p.fields.baseUrl, value: state.baseUrl })
    state.dirty = false
    state.enabled = true
    console.log(`[ARTA:Settings] Saved provider ${providerId}`)
  } catch (err) {
    console.error(`[ARTA:Settings] Failed to save provider ${providerId}:`, err)
  } finally {
    state.saving = false
  }
}

// --- Test connection ---
async function testProvider(providerId: string) {
  const p = providers.find(x => x.id === providerId)!
  const state = providerStates[providerId]
  state.testing = true
  state.testResult = null

  try {
    const baseUrl = state.baseUrl.replace(/\/+$/, '')
    const apiKey = state.apiKey

    if (!apiKey || apiKey.includes('***')) {
      state.testResult = { ok: false, message: 'Please enter a valid API key first' }
      return
    }

    if (providerId === 'openai') {
      // Test OpenAI-compatible: GET /models
      const resp = await axios.get(`${baseUrl}/models`, {
        headers: { Authorization: `Bearer ${apiKey}` },
        timeout: 10000,
      })
      const models = resp.data?.data
      if (Array.isArray(models)) {
        state.testResult = { ok: true, message: `Connected! ${models.length} models available` }
      } else {
        state.testResult = { ok: true, message: 'Connected! (non-standard model list response)' }
      }
    } else if (providerId === 'anthropic') {
      // Test Anthropic: POST /v1/messages with minimal payload
      try {
        await axios.post(
          `${baseUrl}/v1/messages`,
          { model: 'claude-haiku-4-5-20251001', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] },
          { headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' }, timeout: 15000 }
        )
        state.testResult = { ok: true, message: 'Connected! API key is valid' }
      } catch (err: unknown) {
        if (axios.isAxiosError(err) && err.response) {
          // 401 = bad key, anything else means we reached the server
          if (err.response.status === 401) {
            state.testResult = { ok: false, message: 'Invalid API key (401 Unauthorized)' }
          } else {
            // 400, 429, etc. still mean connection works
            state.testResult = { ok: true, message: `Connected! (server returned ${err.response.status})` }
          }
        } else {
          throw err
        }
      }
    }
  } catch (err: unknown) {
    const msg = axios.isAxiosError(err)
      ? (err.response?.data?.error?.message || err.message)
      : (err instanceof Error ? err.message : String(err))
    state.testResult = { ok: false, message: `Connection failed: ${msg}` }
  } finally {
    state.testing = false
  }
}

// --- Save model role ---
async function saveModelRole(role: ModelRole) {
  role.saving = true
  try {
    await settingsApi.update({ key: role.key, value: role.value })
    role.dirty = false
    console.log(`[ARTA:Settings] Saved model role ${role.key} = ${role.value}`)
  } catch (err) {
    console.error(`[ARTA:Settings] Failed to save model role ${role.key}:`, err)
  } finally {
    role.saving = false
  }
}

// --- Save extra key ---
async function saveExtraKey(ek: { key: string; value: string; saving: boolean; dirty: boolean }) {
  ek.saving = true
  try {
    await settingsApi.update({ key: ek.key, value: ek.value, is_sensitive: true })
    ek.dirty = false
  } catch (err) {
    console.error(`[ARTA:Settings] Failed to save ${ek.key}:`, err)
  } finally {
    ek.saving = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="max-w-3xl">
    <h1 class="text-xl font-semibold text-[var(--text-primary)] mb-1">Settings</h1>
    <p class="text-sm text-[var(--text-secondary)] mb-6">
      Configure LLM providers, model assignments, and API keys.
    </p>

    <!-- Loading skeleton -->
    <div v-if="!loaded" class="space-y-4">
      <div v-for="i in 2" :key="i" class="h-48 rounded-xl bg-[var(--glass-bg)] animate-pulse" />
    </div>

    <template v-else>
      <!-- ==================== PROVIDERS ==================== -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
          LLM Providers
        </h2>

        <div class="space-y-4">
          <div
            v-for="p in providers"
            :key="p.id"
            class="rounded-xl border transition-colors"
            :class="providerStates[p.id].enabled
              ? 'border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/5'
              : 'border-[var(--glass-border)] bg-[var(--glass-bg)]'"
          >
            <!-- Provider header -->
            <div class="flex items-center gap-3 px-5 py-4 border-b border-white/5">
              <span class="text-2xl">{{ p.icon }}</span>
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-[var(--text-primary)]">{{ p.name }}</span>
                  <span
                    v-if="providerStates[p.id].enabled"
                    class="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--success)]/15 text-[var(--success)] font-medium"
                  >
                    CONFIGURED
                  </span>
                </div>
                <p class="text-xs text-[var(--text-muted)] mt-0.5">{{ p.description }}</p>
              </div>
            </div>

            <!-- Provider fields -->
            <div class="px-5 py-4 space-y-3">
              <!-- API Key -->
              <div>
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">API Key</label>
                <input
                  v-model="providerStates[p.id].apiKey"
                  type="password"
                  class="glass-input"
                  :placeholder="providerStates[p.id].enabled ? '••••••••••••••••' : 'sk-... or your API key'"
                  @input="providerStates[p.id].dirty = true; providerStates[p.id].testResult = null"
                />
              </div>

              <!-- Base URL -->
              <div>
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
                  Base URL
                  <span class="text-[var(--text-muted)] font-normal ml-1">
                    (change for local/proxy endpoints)
                  </span>
                </label>
                <input
                  v-model="providerStates[p.id].baseUrl"
                  type="text"
                  class="glass-input font-mono text-xs"
                  :placeholder="p.defaults.baseUrl"
                  @input="providerStates[p.id].dirty = true; providerStates[p.id].testResult = null"
                />
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2 pt-1">
                <button
                  class="glass-btn glass-btn-primary text-sm"
                  :disabled="providerStates[p.id].saving"
                  @click="saveProvider(p.id)"
                >
                  {{ providerStates[p.id].saving ? 'Saving...' : 'Save' }}
                </button>
                <button
                  class="glass-btn text-sm"
                  :disabled="providerStates[p.id].testing"
                  @click="testProvider(p.id)"
                >
                  {{ providerStates[p.id].testing ? 'Testing...' : 'Test Connection' }}
                </button>
                <button
                  class="glass-btn text-sm text-[var(--text-muted)]"
                  @click="providerStates[p.id].baseUrl = p.defaults.baseUrl; providerStates[p.id].dirty = true"
                >
                  Reset URL
                </button>
              </div>

              <!-- Test result -->
              <div
                v-if="providerStates[p.id].testResult"
                class="flex items-start gap-2 px-3 py-2 rounded-lg text-sm"
                :class="providerStates[p.id].testResult!.ok
                  ? 'bg-[var(--success)]/10 text-[var(--success)]'
                  : 'bg-[var(--error)]/10 text-[var(--error)]'"
              >
                <span class="shrink-0 mt-0.5">{{ providerStates[p.id].testResult!.ok ? '✓' : '✗' }}</span>
                <span>{{ providerStates[p.id].testResult!.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== MODEL ROLES ==================== -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">
          Model Assignments
        </h2>
        <p class="text-xs text-[var(--text-muted)] mb-3">
          Specify which model handles each role. Use LiteLLM format, e.g.
          <code class="px-1 py-0.5 rounded bg-white/5">gpt-4o</code>,
          <code class="px-1 py-0.5 rounded bg-white/5">claude-sonnet-4-20250514</code>,
          <code class="px-1 py-0.5 rounded bg-white/5">anthropic/claude-haiku-4-5-20251001</code>
        </p>

        <div class="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] divide-y divide-white/5">
          <div
            v-for="role in modelRoles"
            :key="role.key"
            class="flex items-center gap-4 px-5 py-3"
          >
            <div class="w-24 shrink-0">
              <span class="text-sm font-medium text-[var(--text-primary)]">{{ role.label }}</span>
              <p class="text-[10px] text-[var(--text-muted)] leading-tight mt-0.5">{{ role.description }}</p>
            </div>
            <input
              v-model="role.value"
              type="text"
              class="glass-input flex-1 text-sm"
              placeholder="e.g. gpt-4o"
              @input="role.dirty = true"
              @keydown.enter="saveModelRole(role)"
            />
            <button
              class="glass-btn text-xs shrink-0"
              :class="role.dirty ? 'glass-btn-primary' : ''"
              :disabled="role.saving || !role.value"
              @click="saveModelRole(role)"
            >
              {{ role.saving ? '...' : role.dirty ? 'Save' : 'Saved' }}
            </button>
          </div>
        </div>
      </section>

      <!-- ==================== EXTRA KEYS ==================== -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
          Data Source Keys
        </h2>

        <div class="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)]">
          <div
            v-for="ek in extraKeys"
            :key="ek.key"
            class="flex items-center gap-4 px-5 py-3"
          >
            <label class="w-32 shrink-0 text-sm text-[var(--text-primary)]">{{ ek.label }}</label>
            <input
              v-model="ek.value"
              type="password"
              class="glass-input flex-1 text-sm"
              placeholder="Enter key..."
              @input="ek.dirty = true"
              @keydown.enter="saveExtraKey(ek)"
            />
            <button
              class="glass-btn text-xs shrink-0"
              :class="ek.dirty ? 'glass-btn-primary' : ''"
              :disabled="ek.saving || !ek.value"
              @click="saveExtraKey(ek)"
            >
              {{ ek.saving ? '...' : ek.dirty ? 'Save' : 'Saved' }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
