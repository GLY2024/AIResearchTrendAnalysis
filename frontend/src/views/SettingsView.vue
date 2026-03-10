<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { settingsApi } from '@/composables/useApi'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'

interface Provider {
  id: string
  name: string
  description: string
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
  storedKeyMask: string
  baseUrl: string
  hasStoredKey: boolean
  testing: boolean
  testResult: { ok: boolean; message: string } | null
  saving: boolean
  dirty: boolean
  collapsed: boolean
}

interface ExtraKeyState {
  key: string
  label: string
  value: string
  storedValueMask: string
  hasStoredValue: boolean
  saving: boolean
  dirty: boolean
}

interface ModelRole {
  key: string
  label: string
  description: string
  value: string
  provider: string
  saving: boolean
  dirty: boolean
  modelOptions: { id: string; name: string }[]
  loadingModels: boolean
  modelError: string
  showCustom: boolean
}

const providers: Provider[] = [
  {
    id: 'openai',
    name: 'OpenAI compatible',
    description: 'OpenAI, DeepBricks, vLLM, and any endpoint that speaks the OpenAI API.',
    fields: { apiKey: 'openai_api_key', baseUrl: 'openai_base_url' },
    defaults: { baseUrl: 'https://api.openai.com/v1' },
  },
  {
    id: 'anthropic',
    name: 'Anthropic compatible',
    description: 'Claude family endpoints and Anthropic-compatible gateways.',
    fields: { apiKey: 'anthropic_api_key', baseUrl: 'anthropic_base_url' },
    defaults: { baseUrl: 'https://api.anthropic.com/v1' },
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: 'Route across multiple frontier and open models with a single API key.',
    fields: { apiKey: 'openrouter_api_key', baseUrl: 'openrouter_base_url' },
    defaults: { baseUrl: 'https://openrouter.ai/api/v1' },
  },
]

const providerStates = reactive<Record<string, ProviderState>>({})
for (const provider of providers) {
  providerStates[provider.id] = {
    apiKey: '',
    storedKeyMask: '',
    baseUrl: provider.defaults.baseUrl,
    hasStoredKey: false,
    testing: false,
    testResult: null,
    saving: false,
    dirty: false,
    collapsed: false,
  }
}

function makeRole(key: string, label: string, description: string): ModelRole {
  return {
    key,
    label,
    description,
    value: '',
    provider: '',
    saving: false,
    dirty: false,
    modelOptions: [],
    loadingModels: false,
    modelError: '',
    showCustom: false,
  }
}

const modelRoles = ref<ModelRole[]>([
  makeRole('model_chat', 'Chat', 'General conversation and topic framing'),
  makeRole('model_planner', 'Planner', 'Search strategy and query design'),
  makeRole('model_analyst', 'Analyst', 'Interpretation of charts and patterns'),
  makeRole('model_publisher', 'Publisher', 'Report drafting and structure'),
  makeRole('model_executor', 'Executor', 'Search execution and tool-facing work'),
])

const extraKeys = ref<ExtraKeyState[]>([
  { key: 'scopus_api_key', label: 'Scopus API key', value: '', storedValueMask: '', hasStoredValue: false, saving: false, dirty: false },
])

const loaded = ref(false)
const backendState = useBackendState()
const pageError = ref('')
const showOnboarding = ref(false)
const outputLanguage = ref<'zh-CN' | 'en-US'>('zh-CN')
const outputLanguageDirty = ref(false)
const outputLanguageSaving = ref(false)

const configuredProvidersCount = () => providers.filter((provider) => providerState(provider.id).hasStoredKey).length
const assignedRolesCount = () => modelRoles.value.filter((role) => role.provider && role.value).length
const configuredSourceKeysCount = () => extraKeys.value.filter((key) => key.hasStoredValue).length

function providerState(providerId: string): ProviderState {
  return providerStates[providerId]!
}

function resetProviderState(provider: Provider) {
  const state = providerState(provider.id)
  state.apiKey = ''
  state.storedKeyMask = ''
  state.baseUrl = provider.defaults.baseUrl
  state.hasStoredKey = false
  state.testing = false
  state.testResult = null
  state.saving = false
  state.dirty = false
  state.collapsed = false
}

async function loadSettings() {
  pageError.value = ''
  try {
    const settings = await settingsApi.list()
    const map = new Map(settings.map((setting: { key: string; value: string }) => [setting.key, setting.value]))

    let hasAnyKey = false
    for (const provider of providers) {
      resetProviderState(provider)
      const state = providerState(provider.id)
      const apiKey = map.get(provider.fields.apiKey)
      const baseUrl = map.get(provider.fields.baseUrl)

      if (apiKey) {
        state.storedKeyMask = apiKey
        state.hasStoredKey = true
        state.collapsed = true
        hasAnyKey = true
      }
      if (baseUrl) state.baseUrl = baseUrl
    }

    for (const role of modelRoles.value) {
      const value = map.get(role.key)
      if (value) role.value = value
      const providerValue = map.get(`${role.key}_provider`)
      if (providerValue) role.provider = providerValue
    }

    for (const extraKey of extraKeys.value) {
      const value = map.get(extraKey.key)
      extraKey.value = ''
      extraKey.storedValueMask = value ?? ''
      extraKey.hasStoredValue = Boolean(value)
      extraKey.dirty = false
    }

    outputLanguage.value = (map.get('output_language') as 'zh-CN' | 'en-US') || 'zh-CN'
    outputLanguageDirty.value = false

    showOnboarding.value = !hasAnyKey

    for (const role of modelRoles.value) {
      if (role.provider) void fetchModelsForRole(role)
    }
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : 'Failed to load settings.'
    await checkBackend(true)
  } finally {
    loaded.value = true
  }
}

function applyDeepBricksPreset() {
  const state = providerState('openai')
  state.baseUrl = 'https://api.deepbricks.ai/v1'
  state.dirty = true
  state.collapsed = false
}

async function saveProvider(providerId: string) {
  const provider = providers.find((item) => item.id === providerId)!
  const state = providerState(providerId)

  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('provider settings')
    return
  }

  state.saving = true
  try {
    const trimmedApiKey = state.apiKey.trim()
    if (!trimmedApiKey && !state.hasStoredKey) {
      pageError.value = `Enter an API key before saving ${provider.name}.`
      return
    }

    if (trimmedApiKey) {
      const response = await settingsApi.update({ key: provider.fields.apiKey, value: trimmedApiKey, is_sensitive: true })
      state.storedKeyMask = response.value
      state.hasStoredKey = true
      state.apiKey = ''
    }

    await settingsApi.update({ key: provider.fields.baseUrl, value: state.baseUrl })
    state.dirty = false
    state.testResult = null
    showOnboarding.value = false
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : `Failed to save provider ${providerId}.`
    await checkBackend(true)
  } finally {
    state.saving = false
  }
}

async function testProvider(providerId: string) {
  const provider = providers.find((item) => item.id === providerId)!
  const state = providerState(providerId)

  pageError.value = ''
  state.testing = true
  state.testResult = null

  try {
    if (backendState.status !== 'online') {
      state.testResult = { ok: false, message: getBackendOfflineMessage('API key validation') }
      return
    }

    const trimmedApiKey = state.apiKey.trim()
    if (trimmedApiKey) {
      const response = await settingsApi.validate({
        key: provider.fields.apiKey,
        value: trimmedApiKey,
        base_url: state.baseUrl,
      })

      state.testResult = {
        ok: response.valid,
        message: response.message,
      }
      return
    }

    if (!state.hasStoredKey) {
      state.testResult = { ok: false, message: 'Enter a fresh API key before testing the connection.' }
      return
    }

    const response = await settingsApi.fetchModels(providerId)
    state.testResult = {
      ok: !response.error,
      message: response.error ? response.error : `Connection looks healthy. ${response.models.length} models discovered.`,
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    state.testResult = { ok: false, message: `Connection failed: ${message}` }
    await checkBackend(true)
  } finally {
    state.testing = false
  }
}

async function saveModelRole(role: ModelRole) {
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('model assignment updates')
    return
  }
  if (!role.provider) {
    pageError.value = 'Choose a provider before saving this model assignment.'
    return
  }
  if (!providerState(role.provider).hasStoredKey) {
    pageError.value = 'Save the provider API key before assigning models.'
    return
  }

  role.saving = true
  try {
    await Promise.all([
      settingsApi.update({ key: role.key, value: role.value }),
      settingsApi.update({ key: `${role.key}_provider`, value: role.provider }),
    ])
    role.dirty = false
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : `Failed to save ${role.key}.`
    await checkBackend(true)
  } finally {
    role.saving = false
  }
}

function applyToAllRoles() {
  const first = modelRoles.value[0]
  if (!first?.provider || !first.value) return

  for (const role of modelRoles.value.slice(1)) {
    role.provider = first.provider
    role.value = first.value
    role.dirty = true
  }
}

async function fetchModelsForRole(role: ModelRole) {
  if (!role.provider) {
    role.modelOptions = []
    role.modelError = ''
    return
  }
  if (!providerState(role.provider).hasStoredKey) {
    role.modelOptions = []
    role.modelError = 'Save this provider before fetching its model list.'
    return
  }

  role.loadingModels = true
  role.modelError = ''
  role.modelOptions = []
  try {
    const response = await settingsApi.fetchModels(role.provider)
    role.modelOptions = response.models
    if (response.error) role.modelError = response.error
    if (role.value && !response.models.find((model) => model.id === role.value)) {
      role.showCustom = true
    }
  } catch (err) {
    role.modelError = err instanceof Error ? err.message : 'Failed to fetch models.'
    role.modelOptions = []
  } finally {
    role.loadingModels = false
  }
}

function enabledProviders() {
  return providers.filter((provider) => providerState(provider.id).hasStoredKey)
}

async function saveExtraKey(extraKey: ExtraKeyState) {
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('data source key updates')
    return
  }

  extraKey.saving = true
  try {
    const trimmedValue = extraKey.value.trim()
    if (!trimmedValue && !extraKey.hasStoredValue) {
      pageError.value = `Enter ${extraKey.label} before saving.`
      return
    }
    if (trimmedValue) {
      const response = await settingsApi.update({ key: extraKey.key, value: trimmedValue, is_sensitive: true })
      extraKey.storedValueMask = response.value
      extraKey.hasStoredValue = true
      extraKey.value = ''
    }
    extraKey.dirty = false
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : `Failed to save ${extraKey.key}.`
    await checkBackend(true)
  } finally {
    extraKey.saving = false
  }
}

async function saveOutputLanguage() {
  pageError.value = ''
  if (backendState.status !== 'online') {
    pageError.value = getBackendOfflineMessage('output defaults')
    return
  }

  outputLanguageSaving.value = true
  try {
    await settingsApi.update({ key: 'output_language', value: outputLanguage.value })
    outputLanguageDirty.value = false
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : 'Failed to save output language.'
    await checkBackend(true)
  } finally {
    outputLanguageSaving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero">
      <div class="page-hero__kicker">Configuration</div>
      <h2 class="page-hero__title">Control providers, models, and keys from one coherent panel.</h2>
      <p class="page-hero__copy">
        I restructured this page to make the setup story easier to explain: provider access first, model routing second, external source keys last.
      </p>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-card__label">Configured providers</span>
          <span class="stat-card__value">{{ configuredProvidersCount() }}</span>
          <span class="stat-card__hint">Provider slots with a saved key or endpoint</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Assigned roles</span>
          <span class="stat-card__value">{{ assignedRolesCount() }}</span>
          <span class="stat-card__hint">Model routes currently wired into the workflow</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">Source keys</span>
          <span class="stat-card__value">{{ configuredSourceKeysCount() }}</span>
          <span class="stat-card__hint">Optional data source credentials already stored</span>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">State</span>
          <span class="stat-card__value text-[1.1rem]">{{ showOnboarding ? 'Needs setup' : 'Operational' }}</span>
          <span class="stat-card__hint">Whether the app has at least one LLM provider configured</span>
        </div>
      </div>
    </section>

    <div v-if="showOnboarding" class="callout callout--accent">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div class="text-sm font-semibold text-[var(--text-primary)]">First-run setup required</div>
          <div class="mt-1 text-sm text-[var(--text-secondary)]">
            Configure at least one LLM provider and map a model to the workflow roles below.
          </div>
        </div>
        <span class="capsule">Start with OpenAI-compatible or OpenRouter</span>
      </div>
    </div>

    <div class="callout callout--warm">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div class="text-sm font-semibold text-[var(--text-primary)]">DeepBricks quick preset</div>
          <div class="mt-1 text-sm text-[var(--text-secondary)]">
            If you want me to debug against DeepBricks later, I will use the OpenAI-compatible slot with base URL
            <code class="rounded bg-black/20 px-1.5 py-0.5">https://api.deepbricks.ai/v1</code>.
          </div>
        </div>
        <button class="glass-btn glass-btn-warm" @click="applyDeepBricksPreset">
          Apply DeepBricks base URL
        </button>
      </div>
    </div>

    <div
      v-if="pageError"
      class="callout border border-[var(--error)]/25 bg-[var(--error)]/10 text-sm text-[var(--error)]"
    >
      {{ pageError }}
    </div>

    <div v-if="!loaded" class="space-y-4">
      <div v-for="index in 2" :key="index" class="h-48 rounded-[28px] bg-white/[0.04] animate-pulse" />
    </div>

    <template v-else>
      <section class="space-y-4">
        <div>
          <div class="page-hero__kicker mb-3">Provider access</div>
          <h3 class="section-heading">LLM providers</h3>
          <p class="section-copy">Save credentials, point to a custom base URL if needed, then verify the connection before assigning models.</p>
        </div>

        <div class="space-y-4">
          <div
            v-for="provider in providers"
            :key="provider.id"
            class="glass-card overflow-hidden"
          >
            <button
              class="flex w-full items-center gap-4 px-5 py-5 text-left"
              @click="providerState(provider.id).collapsed = !providerState(provider.id).collapsed"
            >
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-base font-semibold text-[var(--text-primary)]">{{ provider.name }}</span>
                  <span v-if="providerState(provider.id).hasStoredKey" class="badge badge-success">Configured</span>
                </div>
                <p class="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{{ provider.description }}</p>
                <div class="mt-3 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                  <span v-if="providerState(provider.id).hasStoredKey" class="capsule">Stored key {{ providerState(provider.id).storedKeyMask }}</span>
                  <span v-else class="capsule">No key saved yet</span>
                  <span class="capsule">{{ providerState(provider.id).baseUrl }}</span>
                </div>
              </div>

              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                class="shrink-0 text-[var(--text-muted)] transition-transform"
                :class="!providerState(provider.id).collapsed ? 'rotate-180' : ''"
              >
                <path d="M4 6l4 4 4-4" />
              </svg>
            </button>

            <div v-if="!providerState(provider.id).collapsed" class="space-y-4 border-t border-white/8 px-5 py-5">
              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">API key</label>
                <input
                  v-model="providerState(provider.id).apiKey"
                  type="password"
                  class="glass-input"
                  :placeholder="providerState(provider.id).hasStoredKey ? 'Leave blank to keep the saved key, or paste a replacement key.' : 'Paste a provider API key here'"
                  @input="providerState(provider.id).dirty = true; providerState(provider.id).testResult = null"
                />
                <p v-if="providerState(provider.id).hasStoredKey" class="mt-2 text-xs text-[var(--text-muted)]">
                  Current saved key: {{ providerState(provider.id).storedKeyMask }}
                </p>
              </div>

              <div>
                <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                  Base URL
                </label>
                <input
                  v-model="providerState(provider.id).baseUrl"
                  type="text"
                  class="glass-input font-mono text-sm"
                  :placeholder="provider.defaults.baseUrl"
                  @input="providerState(provider.id).dirty = true; providerState(provider.id).testResult = null"
                />
              </div>

              <div class="flex flex-wrap gap-2">
                <button
                  class="glass-btn glass-btn-primary"
                  :disabled="providerState(provider.id).saving || backendState.status !== 'online'"
                  @click="saveProvider(provider.id)"
                >
                  {{ providerState(provider.id).saving ? 'Saving...' : 'Save provider' }}
                </button>
                <button
                  class="glass-btn"
                  :disabled="providerState(provider.id).testing || backendState.status !== 'online'"
                  @click="testProvider(provider.id)"
                >
                  {{ providerState(provider.id).testing ? 'Testing...' : 'Test connection' }}
                </button>
                <button
                  class="glass-btn"
                  @click="providerState(provider.id).baseUrl = provider.defaults.baseUrl; providerState(provider.id).dirty = true"
                >
                  Reset URL
                </button>
              </div>

              <div
                v-if="providerState(provider.id).testResult"
                class="callout"
                :class="providerState(provider.id).testResult!.ok ? 'callout--success' : 'border border-[var(--error)]/25 bg-[var(--error)]/10'"
              >
                <span>{{ providerState(provider.id).testResult!.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="space-y-4">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div class="page-hero__kicker mb-3">Routing</div>
            <h3 class="section-heading">Model assignments</h3>
            <p class="section-copy">Assign a provider and model to each stage of the pipeline. You can also use one model across all roles.</p>
          </div>

          <button
            v-if="modelRoles[0]?.provider && modelRoles[0]?.value"
            class="glass-btn"
            @click="applyToAllRoles"
          >
            Use chat model for all roles
          </button>
        </div>

        <div class="space-y-3">
          <div
            v-for="role in modelRoles"
            :key="role.key"
            class="glass-card p-5"
          >
            <div class="grid gap-4 xl:grid-cols-[220px_180px_minmax(0,1fr)_120px] xl:items-center">
              <div>
                <div class="text-sm font-semibold text-[var(--text-primary)]">{{ role.label }}</div>
                <div class="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{{ role.description }}</div>
              </div>

              <select
                v-model="role.provider"
                class="glass-input text-sm"
                @change="role.dirty = true; role.value = ''; fetchModelsForRole(role)"
              >
                <option value="" disabled>Select provider</option>
                <option v-for="provider in enabledProviders()" :key="provider.id" :value="provider.id">
                  {{ provider.name }}
                </option>
              </select>

              <div class="min-w-0">
                <div v-if="role.loadingModels" class="glass-input flex items-center text-sm text-[var(--text-muted)]">
                  Loading models...
                </div>
                <template v-else>
                  <div v-if="!role.showCustom" class="flex gap-2">
                    <select
                      v-model="role.value"
                      class="glass-input flex-1 text-sm"
                      :disabled="!role.provider"
                      @change="role.dirty = true"
                    >
                      <option value="" disabled>Select model</option>
                      <option v-for="model in role.modelOptions" :key="model.id" :value="model.id">
                        {{ model.id }}
                      </option>
                      <option v-if="role.value && !role.modelOptions.find((model) => model.id === role.value)" :value="role.value">
                        {{ role.value }} (custom)
                      </option>
                    </select>
                    <button class="glass-btn" title="Switch to custom input" @click="role.showCustom = true">
                      Custom
                    </button>
                  </div>

                  <div v-else class="flex gap-2">
                    <input
                      v-model="role.value"
                      type="text"
                      class="glass-input flex-1 text-sm"
                      placeholder="Type a custom model id"
                      @input="role.dirty = true"
                      @keydown.enter="saveModelRole(role)"
                    />
                    <button class="glass-btn" title="Back to dropdown" @click="role.showCustom = false">
                      List
                    </button>
                  </div>
                </template>

                <p v-if="role.modelError" class="mt-2 text-xs text-[var(--error)]">
                  {{ role.modelError }}
                </p>
              </div>

              <button
                class="glass-btn"
                :class="role.dirty ? 'glass-btn-primary' : ''"
                :disabled="role.saving || !role.value || !role.provider || backendState.status !== 'online'"
                @click="saveModelRole(role)"
              >
                {{ role.saving ? 'Saving...' : role.dirty ? 'Save' : 'Saved' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="space-y-4">
        <div>
          <div class="page-hero__kicker mb-3">Output defaults</div>
          <h3 class="section-heading">Report language</h3>
          <p class="section-copy">Set the default language for AI interpretations and generated reports.</p>
        </div>

        <div class="glass-card p-5">
          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_140px] lg:items-end">
            <div>
              <label class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Default output language</label>
              <select
                v-model="outputLanguage"
                class="glass-input text-sm"
                @change="outputLanguageDirty = true"
              >
                <option value="zh-CN">Simplified Chinese</option>
                <option value="en-US">English</option>
              </select>
              <p class="mt-2 text-xs text-[var(--text-muted)]">
                This now drives analysis interpretation and report generation.
              </p>
            </div>

            <button
              class="glass-btn"
              :class="outputLanguageDirty ? 'glass-btn-primary' : ''"
              :disabled="outputLanguageSaving || backendState.status !== 'online'"
              @click="saveOutputLanguage"
            >
              {{ outputLanguageSaving ? 'Saving...' : outputLanguageDirty ? 'Save' : 'Saved' }}
            </button>
          </div>
        </div>
      </section>

      <section class="space-y-4">
        <div>
          <div class="page-hero__kicker mb-3">External data</div>
          <h3 class="section-heading">Data source keys</h3>
          <p class="section-copy">Optional credentials for premium search sources can be stored here.</p>
        </div>

        <div class="glass-card p-5">
          <div
            v-for="extraKey in extraKeys"
            :key="extraKey.key"
            class="grid gap-3 border-b border-white/8 py-4 last:border-b-0 first:pt-0 last:pb-0 lg:grid-cols-[200px_minmax(0,1fr)_120px] lg:items-center"
          >
            <div>
              <div class="text-sm font-semibold text-[var(--text-primary)]">{{ extraKey.label }}</div>
              <div class="mt-1 text-sm text-[var(--text-secondary)]">Saved as an encrypted sensitive setting.</div>
              <div v-if="extraKey.hasStoredValue" class="mt-2 text-xs text-[var(--text-muted)]">
                Current saved value: {{ extraKey.storedValueMask }}
              </div>
            </div>

            <input
              v-model="extraKey.value"
              type="password"
              class="glass-input text-sm"
              :placeholder="extraKey.hasStoredValue ? 'Leave blank to keep the saved key, or paste a replacement key.' : 'Enter key...'"
              @input="extraKey.dirty = true"
              @keydown.enter="saveExtraKey(extraKey)"
            />

            <button
              class="glass-btn"
              :class="extraKey.dirty ? 'glass-btn-primary' : ''"
              :disabled="extraKey.saving || backendState.status !== 'online'"
              @click="saveExtraKey(extraKey)"
            >
              {{ extraKey.saving ? 'Saving...' : extraKey.dirty ? 'Save' : 'Saved' }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
