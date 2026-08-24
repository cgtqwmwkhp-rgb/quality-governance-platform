/**
 * Entity360 API client (conveyor X-1).
 *
 * Shared hop contract for Connections / ImpactBundle. Every route 404s while
 * `entity_360` is closed. Doc Graph is not the Golden Thread.
 */
import type { AxiosInstance, AxiosResponse } from 'axios'

export type Entity360HopOrigin = 'graph' | 'cel' | 'case_link' | 'job' | 'lifecycle'
export type Entity360HopDirection = 'upstream' | 'downstream'
export type Entity360SourceStatusName = 'ok' | 'denied' | 'error' | 'skipped'

export interface Entity360Hop {
  source_type: string
  source_id: number
  title?: string | null
  reference?: string | null
  href: string
  direction: Entity360HopDirection
  relation: string
  depth: number
  origin: Entity360HopOrigin | string
  status?: string | null
  confidence?: number | null
  edge_id?: number | null
  version_pin?: number | null
}

export interface Entity360EntityRef {
  source_type: string
  source_id: number
  href: string
  title?: string | null
  reference?: string | null
}

export interface Entity360SourceStatus {
  origin: string
  status: Entity360SourceStatusName
}

export interface Entity360Bundle {
  entity: Entity360EntityRef
  upstream: Entity360Hop[]
  downstream: Entity360Hop[]
  sources: Entity360SourceStatus[]
  complete: boolean
  degraded_reasons: string[]
  generated_at: string
}

export interface ImpactBundle extends Entity360Bundle {
  kind: 'impact_bundle'
  can_publish: boolean
  hops: Entity360Hop[]
}

const PREFIX = '/api/v1/entity-360'

export function createEntity360Api(api: AxiosInstance) {
  return {
    getBundle(
      entityType: string,
      entityId: number,
    ): Promise<AxiosResponse<Entity360Bundle>> {
      return api.get(`${PREFIX}/${encodeURIComponent(entityType)}/${entityId}`)
    },

    getDocumentImpact(documentId: number): Promise<AxiosResponse<ImpactBundle>> {
      return api.get(`${PREFIX}/documents/${documentId}/impact`)
    },
  }
}

export type Entity360Api = ReturnType<typeof createEntity360Api>
