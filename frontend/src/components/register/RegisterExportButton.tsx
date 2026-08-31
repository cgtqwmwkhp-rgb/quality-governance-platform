import { useState } from 'react'
import { Download } from 'lucide-react'
import { Button } from '../ui/Button'
import { toast } from '../../contexts/ToastContext'
import { downloadModuleExport } from '../../utils/moduleExportDownload'
import type { RegisterExportOverlay } from './registerExportOverlay'

interface RegisterExportButtonProps {
  docRef: string
  overlay: RegisterExportOverlay
  /** A server filter is narrowing the list on screen; the export cannot reproduce it. */
  serverFilterApplied?: boolean
}

/**
 * "Export this register" on a captioned list — the Export Center module export
 * with the PEL reference tagged onto the filename. There is no per-register dump
 * job, so the note says plainly what the file contains.
 */
export default function RegisterExportButton({
  docRef,
  overlay,
  serverFilterApplied = false,
}: RegisterExportButtonProps) {
  const [exporting, setExporting] = useState(false)
  const noteId = `register-export-note-${docRef}`

  const handleExport = async () => {
    setExporting(true)
    try {
      const { filename, truncated } = await downloadModuleExport({
        module: overlay.module,
        format: 'csv',
        register: docRef,
      })
      toast.success(
        truncated
          ? `${filename} downloaded — row cap reached, so this is not the whole ${overlay.moduleLabel} module.`
          : `${filename} downloaded — whole ${overlay.moduleLabel} module.`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="mt-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        data-testid="register-export-btn"
        aria-describedby={noteId}
        disabled={exporting}
        onClick={() => void handleExport()}
      >
        <Download className="w-4 h-4" aria-hidden />
        {exporting ? 'Exporting…' : 'Export this register (CSV)'}
      </Button>
      <p id={noteId} className="text-muted-foreground mt-1" data-testid="register-export-note">
        Uses the Export Center {overlay.moduleLabel} export and tags the filename {docRef}. The
        file is the whole {overlay.moduleLabel} module — not a separate {docRef} extract, and not a
        copy of the filters on this screen. An empty module downloads a header row only.
        {serverFilterApplied
          ? ' The server filter named above is not applied to the file, so it will hold more rows than this list.'
          : ''}
      </p>
    </div>
  )
}
