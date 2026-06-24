import { invoke } from '@tauri-apps/api/core'

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

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export async function loadConfig(): Promise<AppConfig> {
  if (!isTauri) return { ...DEFAULT_CONFIG }

  try {
    const json = await invoke<string>('load_secure_config')
    if (!json) return { ...DEFAULT_CONFIG }
    const parsed = JSON.parse(json) as Partial<AppConfig>
    return { ...DEFAULT_CONFIG, ...parsed }
  } catch {
    return { ...DEFAULT_CONFIG }
  }
}

export async function saveConfig(cfg: AppConfig): Promise<void> {
  if (!isTauri) return
  await invoke('save_secure_config', { json: JSON.stringify(cfg) })
}

export function configIsComplete(cfg: AppConfig): boolean {
  const needsApiKey =
    cfg.llmProvider === 'openai' ||
    cfg.llmProvider === 'groq' ||
    cfg.llmProvider === 'mistral'
  if (needsApiKey && !cfg.llmApiKey) return false
  return true
}
