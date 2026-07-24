import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/Dialog'
import { useTranslation } from 'react-i18next'
import GlobalSearchPanel from './GlobalSearchPanel'
import { useGlobalSearch } from './useGlobalSearch'

interface GlobalSearchPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function GlobalSearchPalette({ open, onOpenChange }: GlobalSearchPaletteProps) {
  const { t } = useTranslation()
  const search = useGlobalSearch({
    open,
    autofocus: true,
    onNavigateAway: () => onOpenChange(false),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl w-[calc(100vw-2rem)] top-[12%] translate-y-0 max-h-[80vh] p-4 sm:p-5">
        <DialogHeader className="pr-8">
          <DialogTitle>{t('search.palette_title', 'Search')}</DialogTitle>
          <DialogDescription>
            {t(
              'search.palette_description',
              'Search across modules without leaving this page. Press Escape to close.',
            )}
          </DialogDescription>
        </DialogHeader>
        <GlobalSearchPanel search={search} compact showHeader={false} />
      </DialogContent>
    </Dialog>
  )
}
