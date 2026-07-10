import { Building2, User } from 'lucide-react'
import type { ExternalAuditImportJob } from '../../api/client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'
import { formatDate } from './importReviewHelpers'

type ImportReviewAuditSummaryProps = {
  job: ExternalAuditImportJob
}

export function ImportReviewAuditSummary({ job }: ImportReviewAuditSummaryProps) {
  const prov = job.provenance_json ?? {}
  const orgName = String(
    job.organization_name ?? prov.organization_name ?? prov.declared_organization_name ?? '',
  )
  const auditorName = String(job.auditor_name ?? prov.auditor_name ?? '')
  const auditType = String(job.audit_type ?? prov.audit_type ?? '')
  const certNo = String(job.certificate_number ?? prov.certificate_number ?? '')
  const scope = String(job.audit_scope ?? prov.audit_scope ?? '')
  const nextDate = String(job.next_audit_date ?? prov.next_audit_date ?? '')
  const siteName = String(prov.site_name ?? '')
  const siteAddr = String(prov.site_address ?? '')
  const hasAny = Boolean(orgName || auditorName || auditType || certNo || scope || nextDate)

  if (!hasAny) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-5 w-5 text-primary" />
          Audit Report Summary
        </CardTitle>
        <CardDescription>
          Key metadata extracted from the audit document by AI analysis.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {orgName ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Organisation audited
            </p>
            <p className="mt-1 font-medium text-foreground">{orgName}</p>
          </div>
        ) : null}
        {siteName ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Site / Facility</p>
            <p className="mt-1 font-medium text-foreground">{siteName}</p>
            {siteAddr ? <p className="mt-1 text-xs text-muted-foreground">{siteAddr}</p> : null}
          </div>
        ) : null}
        {auditorName ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1">
              <User size={12} /> Lead auditor
            </p>
            <p className="mt-1 font-medium text-foreground">{auditorName}</p>
          </div>
        ) : null}
        {auditType ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit type</p>
            <p className="mt-1 font-medium text-foreground capitalize">
              {auditType.replace(/_/g, ' ')}
            </p>
          </div>
        ) : null}
        {certNo ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Certificate / Registration No.
            </p>
            <p className="mt-1 font-medium text-foreground">{certNo}</p>
          </div>
        ) : null}
        {scope ? (
          <div className="col-span-full rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit scope</p>
            <p className="mt-1 text-sm text-foreground line-clamp-4">{scope}</p>
          </div>
        ) : null}
        {nextDate ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Next audit date</p>
            <p className="mt-1 font-medium text-foreground">{formatDate(nextDate)}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
