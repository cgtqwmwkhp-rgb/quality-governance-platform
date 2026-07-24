import { Command } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import GlobalSearchPanel from '../components/search/GlobalSearchPanel'
import { useGlobalSearch } from '../components/search/useGlobalSearch'

export default function GlobalSearch() {
  const { t } = useTranslation()
  const search = useGlobalSearch({ autofocus: true })

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground text-center flex items-center justify-center gap-2">
        <Command className="w-4 h-4" /> + K {t('search.open_from_anywhere', 'to open from anywhere')}
      </p>
      <GlobalSearchPanel search={search} showHeader />
    </div>
  )
}
