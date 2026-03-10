<script setup lang="ts">
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { settingsApi } from '@/composables/useApi'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'

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
  provider: string       // 'openai' | 'anthropic' | ''
  saving: boolean
  dirty: boolean
  modelOptions: { id: string; name: string }[]
  loadingModels: boolean
  modelError: string
  showCustom: boolean    // toggle for custom model input
}

// --- Provider definitions ---
const providers: Provider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4o-mini and compatible APIs (DeepBricks, vLLM, etc.)',
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
    defaults: { baseUrl: 'https://api.anthropic.com/v1' },
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: 'Access 200+ models via unified API (OpenAI, Google, Meta, etc.)',
    icon: '🔀',
    fields: { apiKey: 'openrouter_api_key', baseUrl: 'openrouter_base_url' },
    defaults: { baseUrl: 'https://openrouter.ai/api/v1' },
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

function makeRole(key: string, label: string, description: string): ModelRole {
  return { key, label, description, value: '', provider: '', saving: false, dirty: false, modelOptions: [], loadingModels: false, modelError: '', showCustom: false }
}

const modelRoles = ref<ModelRole[]>([
  makeRole('model_chat', 'Chat', 'General conversation and research discussion'),
  makeRole('model_planner', 'Planner', 'Search strategy and plan generation'),
  makeRole('model_analyst', 'Analyst', 'Data analysis and interpretation'),
  makeRole('model_publisher', 'Publisher', 'Report writing and formatting'),
  makeRole('model_executor', 'Executor', 'Search execution and tool calling'),
])

const extraKeys = ref<{ key: string; label: string; value: string; saving: boolean; dirty: boolean }[]>([
  { key: 'scopus_api_key', label: 'Scopus API Key', value: '', saving: false, dirty: false },
])

const loaded = ref(false)
const backendState = useBackendState()
const pageError = ref('')

function providerState(providerId: string): ProviderState {
  return providerStates[providerId]!
}

// --- Load settings from backend ---
async function loadSettings() {
  pageError.value = ''
  try {
    const settings = await settingsApi.list()
    const map = new Map(settings.map((s: { key: string; value: string }) => [s.key, s.value]))

    for (const p of providers) {
      const state = providerState(p.id)
      const key = map.get(p.fields.apiKey)
      const url = map.get(p.fields.baseUrl)
      if (key) { state.apiKey = key; state.enabled = true }
      if (url) state.baseUrl = url
    }

    for (const role of modelRoles.value) {
      const v = map.get(role.key)
      if (v) role.value = v
      const pv = map.get(`${role.key}_provider`)
      if (pv) role.provider = pv
    }

    for (const ek of extraKeys.value) {
      const v = map.get(ek.key)
      if (v) ek.value = v
    }
  } catch (err) {
    console.error('[ARTA:Settings] Failed to load settings:', err)
    pageError.value = err instanceof Error ? err.message : 'Failed to load settings.'
    await checkBackend(true)
  }
  loaded.value = true
}

// --- Save provider ---
async function saveProvider(providerId: string) {
  const p = providers.find(x => x.id === providerId)!
  const state = providerState(providerId)
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('provider settings')
    return
  }

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
    pageError.value = err instanceof Error ? err.message : `Failed to save provider ${providerId}.`
    await checkBackend(true)
  } finally {
    state.saving = false
  }
}

// --- Test connection ---
async function testProvider(providerId: string) {
  const p = providers.find(x => x.id === providerId)!
  const state = providerState(providerId)
  pageError.value = ''
  state.testing = true
  state.testResult = null

  try {
    const apiKey = state.apiKey

    if (!apiKey || apiKey.includes('***')) {
      state.testResult = { ok: false, message: 'Please enter a valid API key first' }
      return
    }

    if (backendState.status !== 'online') {
      state.testResult = { ok: false, message: getBackendOfflineMessage('API key validation') }
      return
    }

    const resp = await settingsApi.validate({
      key: p.fields.apiKey,
      value: apiKey,
      base_url: state.baseUrl,
    })

    state.testResult = {
      ok: resp.valid,
      message: resp.message,
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    state.testResult = { ok: false, message: `Connection failed: ${msg}` }
    await checkBackend(true)
  } finally {
    state.testing = false
  }
}

// --- Save model role ---
async function saveModelRole(role: ModelRole) {
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('model assignment updates')
    return
  }
  role.saving = true
  try {
    // Save model name and provider in parallel
    await Promise.all([
      settingsApi.update({ key: role.key, value: role.value }),
      settingsApi.update({ key: `${role.key}_provider`, value: role.provider }),
    ])
    role.dirty = false
    console.log(`[ARTA:Settings] Saved model role ${role.key} = ${role.provider}/${role.value}`)
  } catch (err) {
    console.error(`[ARTA:Settings] Failed to save model role ${role.key}:`, err)
    pageError.value = err instanceof Error ? err.message : `Failed to save ${role.key}.`
    await checkBackend(true)
  } finally {
    role.saving = false
  }
}

// Fetch models for a role's selected provider
async function fetchModelsForRole(role: ModelRole) {
  if (!role.provider) {
    role.modelOptions = []
    return
  }
  role.loadingModels = true
  role.modelError = ''
  role.modelOptions = []
  try {
    const resp = await settingsApi.fetchModels(role.provider)
    role.modelOptions = resp.models
    if (resp.error) role.modelError = resp.error
  } catch (err) {
    role.modelError = err instanceof Error ? err.message : 'Failed to fetch models'
    role.modelOptions = []
  } finally {
    role.loadingModels = false
  }
}

// Computed: list of enabled provider ids
function enabledProviders() {
  return providers.filter(p => providerState(p.id).enabled)
}

// --- Save extra key ---
async function saveExtraKey(ek: { key: string; value: string; saving: boolean; dirty: boolean }) {
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('data source key updates')
    return
  }
  ek.saving = true
  try {
    await settingsApi.update({ key: ek.key, value: ek.value, is_sensitive: true })
    ek.dirty = false
  } catch (err) {
    console.error(`[ARTA:Settings] Failed to save ${ek.key}:`, err)
    pageError.value = err instanceof Error ? err.message : `Failed to save ${ek.key}.`
    await checkBackend(true)
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
    <div
      v-if="pageError"
      class="mb-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]"
    >
      {{ pageError }}
    </div>

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
            :class="providerState(p.id).enabled
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
                    v-if="providerState(p.id).enabled"
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
                  v-model="providerState(p.id).apiKey"
                  type="password"
                  class="glass-input"
                  :placeholder="providerState(p.id).enabled ? '••••••••••••••••' : 'sk-... or your API key'"
                  @input="providerState(p.id).dirty = true; providerState(p.id).testResult = null"
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
                  v-model="providerState(p.id).baseUrl"
                  type="text"
                  class="glass-input font-mono text-xs"
                  :placeholder="p.defaults.baseUrl"
                  @input="providerState(p.id).dirty = true; providerState(p.id).testResult = null"
                />
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2 pt-1">
                <button
                  class="glass-btn glass-btn-primary text-sm"
                  :disabled="providerState(p.id).saving || backendState.status !== 'online'"
                  @click="saveProvider(p.id)"
                >
                  {{ providerState(p.id).saving ? 'Saving...' : 'Save' }}
                </button>
                <button
                  class="glass-btn text-sm"
                  :disabled="providerState(p.id).testing || backendState.status !== 'online'"
                  @click="testProvider(p.id)"
                >
                  {{ providerState(p.id).testing ? 'Testing...' : 'Test Connection' }}
                </button>
                <button
                  class="glass-btn text-sm text-[var(--text-muted)]"
                  @click="providerState(p.id).baseUrl = p.defaults.baseUrl; providerState(p.id).dirty = true"
                >
                  Reset URL
                </button>
              </div>

              <!-- Test result -->
              <div
                v-if="providerState(p.id).testResult"
                class="flex items-start gap-2 px-3 py-2 rounded-lg text-sm"
                :class="providerState(p.id).testResult!.ok
                  ? 'bg-[var(--success)]/10 text-[var(--success)]'
                  : 'bg-[var(--error)]/10 text-[var(--error)]'"
              >
                <span class="shrink-0 mt-0.5">{{ providerState(p.id).testResult!.ok ? '✓' : '✗' }}</span>
                <span>{{ providerState(p.id).testResult!.message }}</span>
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
          Select a provider and model for each role. Models are fetched from the provider's API.
        </p>

        <div class="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] divide-y divide-white/5">
          <div
            v-for="role in modelRoles"
            :key="role.key"
            class="px-5 py-3 space-y-2"
          >
            <div class="flex items-center gap-3">
              <!-- Role label -->
              <div class="w-24 shrink-0">
                <span class="text-sm font-medium text-[var(--text-primary)]">{{ role.label }}</span>
                <p class="text-[10px] text-[var(--text-muted)] leading-tight mt-0.5">{{ role.description }}</p>
              </div>

              <!-- Provider dropdown -->
              <select
                v-model="role.provider"
                class="glass-input w-36 text-sm"
                @change="role.dirty = true; role.value = ''; fetchModelsForRole(role)"
              >
                <option value="" disabled>Provider…</option>
                <option
                  v-for="ep in enabledProviders()"
                  :key="ep.id"
                  :value="ep.id"
                >
                  {{ ep.icon }} {{ ep.name }}
                </option>
              </select>

              <!-- Model select / custom input -->
              <div class="flex-1 relative">
                <div v-if="role.loadingModels" class="glass-input text-sm text-[var(--text-muted)] flex items-center">
                  Loading models…
                </div>
                <template v-else>
                  <!-- Dropdown mode -->
                  <div v-if="!role.showCustom" class="flex gap-1">
                    <select
                      v-model="role.value"
                      class="glass-input flex-1 text-sm"
                      @change="role.dirty = true"
                      :disabled="!role.provider"
                    >
                      <option value="" disabled>Select model…</option>
                      <option
                        v-for="m in role.modelOptions"
                        :key="m.id"
                        :value="m.id"
                      >
                        {{ m.id }}
                      </option>
                      <!-- Keep current value visible if not in list -->
                      <option
                        v-if="role.value && !role.modelOptions.find(m => m.id === role.value)"
                        :value="role.value"
                      >
                        {{ role.value }} (custom)
                      </option>
                    </select>
                    <button
                      class="glass-btn text-[10px] shrink-0 px-2"
                      title="Type a custom model name"
                      @click="role.showCustom = true"
                    >
                      ✎
                    </button>
                  </div>
                  <!-- Custom input mode -->
                  <div v-else class="flex gap-1">
                    <input
                      v-model="role.value"
                      type="text"
                      class="glass-input flex-1 text-sm"
                      placeholder="e.g. gemini-2.5-flash"
                      @input="role.dirty = true"
                      @keydown.enter="saveModelRole(role)"
                    />
                    <button
                      class="glass-btn text-[10px] shrink-0 px-2"
                      title="Switch back to dropdown"
                      @click="role.showCustom = false"
                    >
                      ▾
                    </button>
                  </div>
                </template>
              </div>

              <!-- Save button -->
              <button
                class="glass-btn text-xs shrink-0"
                :class="role.dirty ? 'glass-btn-primary' : ''"
                :disabled="role.saving || !role.value || !role.provider || backendState.status !== 'online'"
                @click="saveModelRole(role)"
              >
                {{ role.saving ? '...' : role.dirty ? 'Save' : 'Saved' }}
              </button>
            </div>

            <!-- Model fetch error -->
            <p
              v-if="role.modelError"
              class="text-[10px] text-[var(--error)] pl-[6.5rem]"
            >
              {{ role.modelError }}
            </p>
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
              :disabled="ek.saving || !ek.value || backendState.status !== 'online'"
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
