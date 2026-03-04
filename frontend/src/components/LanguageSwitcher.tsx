import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

const LANGUAGES = [
  { code: 'en', label: 'English' },
] as const;

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
  };

  return (
    <div className="relative flex items-center">
      <Globe className="w-4 h-4 text-muted-foreground absolute left-2 pointer-events-none" />
      <select
        value={i18n.language?.split('-')[0] || 'en'}
        onChange={handleChange}
        aria-label={t('language.switch')}
        className="appearance-none bg-transparent text-sm text-muted-foreground hover:text-foreground pl-7 pr-2 py-1.5 rounded-lg border border-transparent hover:border-border focus:border-primary focus:outline-none cursor-pointer transition-colors"
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  );
}
