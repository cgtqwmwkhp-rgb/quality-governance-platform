import { useTranslation } from 'react-i18next'
import {
  Upload,
  RefreshCw,
  Loader2,
  AlertCircle,
  FileQuestion,
  Eye,
  FileText,
  File,
  Download,
  Trash2,
} from 'lucide-react'
import { type EvidenceAsset, evidenceAssetsApi } from '../../api/client'
import { trackError } from '../../utils/errorTracker'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui/Tooltip'
import { cn } from '../../helpers/utils'

interface InvestigationEvidenceProps {
  evidenceAssets: EvidenceAsset[]
  evidenceLoading: boolean
  evidenceError: string | null
  uploadingEvidence: boolean
  deletingEvidenceId: number | null
  onUploadEvidence: (file: File) => void
  onDeleteEvidence: (assetId: number) => void
  onRefresh: () => void
  onSetEvidenceError: (error: string | null) => void
}

export default function InvestigationEvidence({
  evidenceAssets,
  evidenceLoading,
  evidenceError,
  uploadingEvidence,
  deletingEvidenceId,
  onUploadEvidence,
  onDeleteEvidence,
  onRefresh,
  onSetEvidenceError,
}: InvestigationEvidenceProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">
            {t('investigations.evidence_register')}
          </h3>
          <div className="flex items-center gap-2">
            <input
              type="file"
              id="evidence-upload"
              ref={(el) => {
                if (el)
                  (
                    window as unknown as {
                      __evidenceFileInput?: HTMLInputElement
                    }
                  ).__evidenceFileInput = el
              }}
              className="hidden"
              accept="image/*,video/*,application/pdf,.doc,.docx,.xls,.xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onUploadEvidence(file)
                e.target.value = ''
              }}
              disabled={uploadingEvidence}
            />
            <Button
              variant="default"
              disabled={uploadingEvidence}
              onClick={() => {
                const fileInput = document.getElementById('evidence-upload') as HTMLInputElement
                if (fileInput) fileInput.click()
              }}
            >
              {uploadingEvidence ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {t('investigations.upload_evidence')}
            </Button>
            <Button variant="outline" onClick={onRefresh} disabled={evidenceLoading}>
              <RefreshCw className={cn('w-4 h-4', evidenceLoading && 'animate-spin')} />
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Upload photos, videos, PDFs, or documents as evidence for this investigation. Maximum file
          size: 50MB.
        </p>
      </Card>

      {/* Error Display */}
      {evidenceError && (
        <Card className="p-4 bg-destructive/10 border-destructive/30">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Error:</span>
            <span>{evidenceError}</span>
          </div>
        </Card>
      )}

      {/* Evidence List */}
      {evidenceLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : evidenceAssets.length === 0 ? (
        <Card className="p-12 text-center">
          <FileQuestion className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No Evidence Uploaded</h3>
          <p className="text-muted-foreground max-w-md mx-auto">
            Upload photos, documents, or other files to document evidence for this investigation.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {evidenceAssets.map((asset) => (
            <Card key={asset.id} className="p-4">
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  {asset.asset_type === 'photo' ? (
                    <Eye className="w-6 h-6 text-primary" />
                  ) : asset.asset_type === 'pdf' ? (
                    <FileText className="w-6 h-6 text-primary" />
                  ) : (
                    <File className="w-6 h-6 text-primary" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground truncate">
                    {asset.title || asset.original_filename || 'Untitled'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {asset.asset_type} &bull;{' '}
                    {asset.file_size_bytes
                      ? `${Math.round(asset.file_size_bytes / 1024)}KB`
                      : 'Unknown size'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(asset.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={async () => {
                            try {
                              const response = await evidenceAssetsApi.getSignedUrl(asset.id)
                              window.open(response.data.signed_url, '_blank')
                            } catch (err) {
                              trackError(err, {
                                component: 'InvestigationEvidence',
                                action: 'downloadEvidence',
                              })
                              onSetEvidenceError('Failed to get download URL')
                            }
                          }}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Download</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDeleteEvidence(asset.id)}
                          disabled={deletingEvidenceId === asset.id}
                          className="text-destructive hover:text-destructive"
                        >
                          {deletingEvidenceId === asset.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>
              {asset.description && (
                <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                  {asset.description}
                </p>
              )}
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className="text-xs">
                  {asset.visibility.replace(/_/g, ' ')}
                </Badge>
                {asset.contains_pii && (
                  <Badge variant="destructive" className="text-xs">
                    Contains PII
                  </Badge>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
