// frontend/src/store/appConfig.ts
import { load } from '@tauri-apps/plugin-store'

export type LLMProvider = 'openai' | 'ollama' | 'lmstudio' | 'groq' | 'mistral' | 'compatible'

export interface AppConfig {
  llmProvider: LLMProvider
  llmApiKey: string
  llmModel: string
  llmBaseUrl: string
  llmTemperature: number
  adzunaAppId: string
  adzunaApiKey: string
  adzunaCountry: string
  cvPrompt: string
  clPrompt: string
  cvLanguage: string
  clLanguage: string
}

export const DEFAULT_CONFIG: AppConfig = {
  llmProvider: 'ollama',
  llmApiKey: '',
  llmModel: 'llama3.2',
  llmBaseUrl: 'http://localhost:11434/v1',
  llmTemperature: 0,
  adzunaAppId: '',
  adzunaApiKey: '',
  adzunaCountry: 'de',
  cvPrompt: '',
  clPrompt: '',
  cvLanguage: 'English',
  clLanguage: 'English',
}

async function getStore() {
  return load('config.json')
}

export async function loadConfig(): Promise<AppConfig> {
  const store = await getStore()
  const result: Partial<AppConfig> = {}
  for (const key of Object.keys(DEFAULT_CONFIG) as (keyof AppConfig)[]) {
    const val = await store.get<AppConfig[typeof key]>(key)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(result as any)[key] = val ?? DEFAULT_CONFIG[key]
  }
  return result as AppConfig
}

export async function saveConfig(cfg: AppConfig): Promise<void> {
  const store = await getStore()
  for (const [key, val] of Object.entries(cfg)) {
    await store.set(key, val)
  }
  await store.save()
}

export function configIsComplete(cfg: AppConfig): boolean {
  const needsApiKey = cfg.llmProvider === 'openai' || cfg.llmProvider === 'groq' || cfg.llmProvider === 'mistral'
  if (needsApiKey && !cfg.llmApiKey) return false
  return true
}
