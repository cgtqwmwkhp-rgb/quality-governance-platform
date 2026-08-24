/**
 * Entity360 Connections strip helpers (X-1 / X-3).
 *
 * Flag-gated visibility only — DocumentDetail mounts the strip; fetch lives
 * inside the component. Satellite pages nest under entity_360_satellites.
 */

export function shouldShowEntity360Strip(entity360Enabled: boolean): boolean {
  return Boolean(entity360Enabled)
}

export function shouldFetchEntity360(
  entity360Enabled: boolean,
  masterDocumentGraphEnabled = true,
): boolean {
  // Connections strip uses Entity360; document subjects still benefit from
  // graph producers which independently 404 when Doc Graph is closed
  // (producer marks error/skip). Strip itself is gated by entity_360 only.
  void masterDocumentGraphEnabled
  return Boolean(entity360Enabled)
}

/** Nested gate for satellite module mounts (mirrors job_cell_links). */
export function shouldShowSatelliteConnections(
  entity360Enabled: boolean,
  satellitesEnabled: boolean,
): boolean {
  return Boolean(entity360Enabled && satellitesEnabled)
}

export function hopCaption(hop: {
  title?: string | null
  reference?: string | null
  source_type: string
  source_id: number
}): string {
  if (hop.reference) return String(hop.reference)
  if (hop.title) return String(hop.title)
  return `${hop.source_type} #${hop.source_id}`
}

export function connectionsHasNeighbors(bundle: {
  upstream?: unknown[]
  downstream?: unknown[]
} | null): boolean {
  if (!bundle) return false
  return (bundle.upstream?.length ?? 0) + (bundle.downstream?.length ?? 0) > 0
}
