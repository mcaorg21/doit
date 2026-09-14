import { useLanguage } from './LanguageContext'

// Rendered once in App.tsx, fixed to a corner so it's reachable from every page —
// there's no shared layout/header component across routes (each page is its own
// top-level route element) to hang this off of instead.
export default function LanguageToggle() {
  const { language, setLanguage, t } = useLanguage()

  return (
    <div className="language-toggle" title={t('languageToggleTitle')}>
      <button
        type="button"
        className={language === 'en' ? 'active' : ''}
        onClick={() => setLanguage('en')}
      >
        EN
      </button>
      <button
        type="button"
        className={language === 'pt' ? 'active' : ''}
        onClick={() => setLanguage('pt')}
      >
        PT
      </button>
    </div>
  )
}
