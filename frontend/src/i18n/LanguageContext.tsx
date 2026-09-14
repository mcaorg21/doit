import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { en } from './en'
import { pt } from './pt'

export type Language = 'en' | 'pt'
export type TranslationKey = keyof typeof en

const STORAGE_KEY = 'automation.language'
const dictionaries: Record<Language, Record<TranslationKey, string>> = { en, pt }

function loadLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'en' || stored === 'pt') return stored
  } catch {
    // localStorage unavailable (private mode, etc.) — fall through to default.
  }
  return 'en'
}

interface LanguageContextValue {
  language: Language
  setLanguage: (lang: Language) => void
  t: (key: TranslationKey) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(loadLanguage)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // Best-effort persistence only — a blocked/unavailable localStorage just means
      // the choice resets next visit, not worth surfacing as an error.
    }
  }, [language])

  const setLanguage = useCallback((lang: Language) => setLanguageState(lang), [])

  const t = useCallback((key: TranslationKey) => dictionaries[language][key] ?? dictionaries.en[key] ?? key, [language])

  return <LanguageContext.Provider value={{ language, setLanguage, t }}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider')
  return ctx
}
