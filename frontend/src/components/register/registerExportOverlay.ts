import {
  REGISTER_CATALOGUE,
  type RegisterAllowedRoute,
  type RegisterEntry,
} from '../../data/registerCatalogue'
import type { ExportModuleId } from '../../utils/moduleExportDownload'

/** Export Center module that backs each catalogue route's list. */
const MODULE_BY_ROUTE: Partial<Record<RegisterAllowedRoute, ExportModuleId>> = {
  '/incidents': 'incidents',
  '/complaints': 'complaints',
  '/risk-register': 'risks',
  '/actions': 'actions',
  '/audits': 'audits',
  '/compliance-schedule': 'compliance_schedule',
  '/documents': 'documents',
}

const MODULE_LABEL: Record<ExportModuleId, string> = {
  incidents: 'Incidents',
  rtas: 'Road Traffic Collisions',
  complaints: 'Complaints',
  risks: 'Risks',
  audits: 'Audits',
  actions: 'Actions (CAPA)',
  documents: 'Documents (IMS052 Register)',
  compliance_schedule: 'Compliance Schedule',
}

export interface RegisterExportOverlay {
  module: ExportModuleId
  moduleLabel: string
}

function hasServerFilter(entry: RegisterEntry): boolean {
  if (!entry.captionQuery) return false
  return [...new URLSearchParams(entry.captionQuery).keys()].some((key) => key !== 'register')
}

/**
 * Export affordance for one Open, or nothing.
 *
 * "Export this register" is the existing Export Center module export with the PEL
 * reference tagged on. That is only honest where the register's own scope *is* the
 * module, which is what the `live` band means: QGP holds the whole register. A
 * `caption` row names a subset of a bigger module — RIDDOR reports inside
 * incidents, one asbestos clock inside the compliance schedule — so a module
 * export tagged with its reference would claim more than the file holds, and that
 * Open gets no export button. Two further exclusions:
 *
 * - `externalSor`: part of the register lives outside QGP, so the module export is
 *   an incomplete answer no matter how it is labelled.
 * - a `?type=` / `?statutory=` caption query: the export has no matching filter,
 *   so the file would not be the list the reader is looking at.
 */
export function resolveRegisterExport(entry: RegisterEntry): RegisterExportOverlay | undefined {
  if (entry.band !== 'live') return undefined
  if (!entry.to) return undefined
  if (entry.externalSor) return undefined
  if (hasServerFilter(entry)) return undefined
  const module = MODULE_BY_ROUTE[entry.to]
  if (!module) return undefined
  return { module, moduleLabel: MODULE_LABEL[module] }
}

/**
 * Every Open that offers an export. Mirrored by ``REGISTER_EXPORT_MODULE`` in
 * src/domain/services/export_center_service.py, which enforces the same pairing
 * server-side — a reference added here without the backend copy is refused rather
 * than mislabelled.
 */
export const REGISTER_EXPORT_OVERLAYS: ReadonlyArray<{ docRef: string; module: ExportModuleId }> =
  REGISTER_CATALOGUE.flatMap((entry) => {
    const overlay = resolveRegisterExport(entry)
    return overlay ? [{ docRef: entry.docRef, module: overlay.module }] : []
  })
