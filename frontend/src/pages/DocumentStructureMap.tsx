/**
 * Whole-library Structure map (DG-3 + NS-EXP / W8) — cascade explorer.
 *
 * Flag-gated by `document_graph_structure_map` (master `document_graph` also
 * required for fetches). Loads the estate via one `GET /document-graph/cascade`
 * aggregate (documents + confirmed implements + L1–L5 band counts) — never the
 * previous 1+N edge fan-out. Reuses DG-1 `RelationshipsMapView` + X-2 GraphCoach.
 * Never calls Doc Graph the Golden Thread. Never auto-confirms.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { GitBranch, Loader2, ArrowLeft } from 'lucide-react'
import { documentGraphApi, getApiErrorMessage } from '../api/client'
import type {
  CascadeBandSummary,
  CascadeOrphanSummary,
  DocumentEdge,
} from '../api/documentGraphClient'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { GraphCoach, GraphOrientationToggle, RelationshipsMapView } from '../components/graph'
import {
  STRUCTURE_MAP_DEFAULT_ORIENTATION,
  buildStructureMapLabels,
  filterConfirmedImplementsEdges,
  filterStructureMapDocumentsByBand,
  findStructureMapRootIds,
  mapCascadeDocumentsToStructureRefs,
  resolveStructureMapFocusId,
  shouldFetchDocumentStructureMap,
  shouldShowDocumentStructureMap,
  structureMapBandButtonLabel,
  structureMapEmptyCopy,
  structureMapLevelBadge,
  type StructureMapBandFilter,
  type StructureMapDocumentRef,
} from '../components/graph/documentStructureMapHelpers'
import {
  readStoredGraphOrientation,
  resolveGraphOrientation,
  writeStoredGraphOrientation,
  type GraphOrientation,
} from '../components/graph/graphOrientation'

function bandFilterFromSummary(band: CascadeBandSummary): StructureMapBandFilter {
  return band.level == null ? 'unset' : band.level
}

export default function DocumentStructureMap() {
  const structureMapEnabled = useFeatureFlag('document_graph_structure_map')
  const documentGraphEnabled = useFeatureFlag('document_graph')
  const visible = shouldShowDocumentStructureMap(structureMapEnabled)
  const shouldFetch = shouldFetchDocumentStructureMap(documentGraphEnabled, structureMapEnabled)

  const [searchParams, setSearchParams] = useSearchParams()
  const focusParam = Number(searchParams.get('focus'))
  const preferredFocus = Number.isFinite(focusParam) && focusParam > 0 ? focusParam : null

  const [documents, setDocuments] = useState<StructureMapDocumentRef[]>([])
  const [edges, setEdges] = useState<DocumentEdge[]>([])
  const [bands, setBands] = useState<CascadeBandSummary[]>([])
  const [orphans, setOrphans] = useState<CascadeOrphanSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [bandFilter, setBandFilter] = useState<StructureMapBandFilter>('all')
  const [orientation, setOrientation] = useState<GraphOrientation>(() =>
    resolveGraphOrientation(
      readStoredGraphOrientation('document_structure_map'),
      STRUCTURE_MAP_DEFAULT_ORIENTATION,
    ),
  )

  const rootIds = useMemo(() => findStructureMapRootIds(edges), [edges])
  const bandScopedDocuments = useMemo(
    () => filterStructureMapDocumentsByBand(documents, bandFilter),
    [documents, bandFilter],
  )
  const focusId = useMemo(
    () => resolveStructureMapFocusId(preferredFocus, bandScopedDocuments, rootIds),
    [preferredFocus, bandScopedDocuments, rootIds],
  )
  const focusDoc = useMemo(
    () => documents.find((doc) => doc.id === focusId) ?? null,
    [documents, focusId],
  )
  const labels = useMemo(() => buildStructureMapLabels(documents), [documents])
  const focusEdges = useMemo(() => {
    if (focusId == null) return []
    return filterConfirmedImplementsEdges(edges).filter(
      (edge) => edge.src_document_id === focusId || edge.dst_document_id === focusId,
    )
  }, [edges, focusId])

  const filteredDocuments = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const filtered = q
      ? bandScopedDocuments.filter((doc) => {
          const hay =
            `${doc.title} ${doc.reference ?? ''} ${doc.documentType ?? ''} ${doc.parentPel ?? ''}`.toLowerCase()
          return hay.includes(q)
        })
      : bandScopedDocuments
    const rootIdSet = new Set(rootIds)
    return filtered.slice().sort((a, b) => {
      const aIsRoot = rootIdSet.has(a.id)
      const bIsRoot = rootIdSet.has(b.id)
      if (aIsRoot === bIsRoot) return 0
      return aIsRoot ? -1 : 1
    })
  }, [bandScopedDocuments, filter, rootIds])

  const loadCascade = useCallback(async () => {
    if (!shouldFetch) {
      setDocuments([])
      setEdges([])
      setBands([])
      setOrphans(null)
      setError(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await documentGraphApi.getCascade()
      const payload = response.data
      setDocuments(mapCascadeDocumentsToStructureRefs(payload.documents ?? []))
      setEdges(filterConfirmedImplementsEdges(payload.edges ?? []))
      setBands(payload.bands ?? [])
      setOrphans(payload.orphans ?? null)
    } catch (err) {
      setDocuments([])
      setEdges([])
      setBands([])
      setOrphans(null)
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [shouldFetch])

  useEffect(() => {
    void loadCascade()
  }, [loadCascade])

  useEffect(() => {
    if (focusId == null || preferredFocus === focusId) return
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('focus', String(focusId))
        return next
      },
      { replace: true },
    )
  }, [focusId, preferredFocus, setSearchParams])

  if (!visible) {
    return <Navigate to="/documents" replace />
  }

  const selectFocus = (id: number) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('focus', String(id))
        return next
      },
      { replace: true },
    )
  }

  const handleOrientationChange = (next: GraphOrientation) => {
    setOrientation(next)
    writeStoredGraphOrientation('document_structure_map', next)
  }

  const confirmedCount = filterConfirmedImplementsEdges(edges).length
  const orphanTotal =
    (orphans?.unimplemented_policy_count ?? 0) +
    (orphans?.unparented_count ?? 0) +
    (orphans?.uncontrolled_record_count ?? 0)

  return (
    <div className="space-y-6 animate-fade-in" data-testid="document-structure-map">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" asChild className="-ml-2">
            <Link to="/documents" data-testid="structure-map-back">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to library
            </Link>
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <GitBranch className="h-5 w-5 text-primary" aria-hidden />
            <h1 className="text-3xl font-bold text-foreground">Structure map</h1>
            <Badge variant="outline">Cascade L1–L5</Badge>
          </div>
          <p className="text-muted-foreground max-w-2xl">
            Whole-library cascade explorer — pick a focus document to walk Manual → Policy →
            Procedure → SOP → Form on the shared map. One estate aggregate; Doc Graph spine, not
            document-control lineage.
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span data-testid="structure-map-doc-count">{documents.length} documents</span>
            <span aria-hidden>·</span>
            <span data-testid="structure-map-edge-count">
              {confirmedCount} confirmed implements
            </span>
            <span aria-hidden>·</span>
            <span data-testid="structure-map-root-count">{rootIds.length} roots</span>
            {orphanTotal > 0 ? (
              <>
                <span aria-hidden>·</span>
                <span data-testid="structure-map-orphan-count">{orphanTotal} orphans</span>
              </>
            ) : null}
          </div>
        </div>
        <GraphOrientationToggle
          surface="document_structure_map"
          value={orientation}
          defaultValue={STRUCTURE_MAP_DEFAULT_ORIENTATION}
          onChange={handleOrientationChange}
        />
      </div>

      <GraphCoach surface="document_structure_map" />

      {bands.length > 0 ? (
        <div
          className="flex flex-wrap gap-2"
          role="toolbar"
          aria-label="Cascade level bands"
          data-testid="structure-map-bands"
        >
          <Button
            type="button"
            size="sm"
            variant={bandFilter === 'all' ? 'default' : 'outline'}
            onClick={() => setBandFilter('all')}
            data-testid="structure-map-band-all"
          >
            All ({documents.length})
          </Button>
          {bands.map((band) => {
            const key = band.level == null ? 'unset' : String(band.level)
            const filterValue = bandFilterFromSummary(band)
            return (
              <Button
                key={key}
                type="button"
                size="sm"
                variant={bandFilter === filterValue ? 'default' : 'outline'}
                onClick={() => setBandFilter(filterValue)}
                data-testid={`structure-map-band-${key}`}
              >
                {structureMapBandButtonLabel(band)}
              </Button>
            )
          })}
        </div>
      ) : null}

      {error ? (
        <div
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
          data-testid="structure-map-error"
        >
          {error}
        </div>
      ) : null}

      {loading && documents.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          Loading cascade structure…
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(240px,320px)_1fr]">
          <Card className="p-4 space-y-3" data-testid="structure-map-picker">
            <div className="space-y-1">
              <h2 className="text-sm font-medium text-foreground">Library focus</h2>
              <p className="text-xs text-muted-foreground">
                Roots listed first when known. Filter by cascade band or search title / PEL.
              </p>
            </div>
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter by title or reference"
              aria-label="Filter library documents"
              data-testid="structure-map-filter"
            />
            <ul
              className="max-h-[28rem] space-y-1 overflow-y-auto"
              data-testid="structure-map-doc-list"
            >
              {filteredDocuments.length === 0 ? (
                <li className="text-sm text-muted-foreground px-1 py-2">
                  {filter.trim() || bandFilter !== 'all'
                    ? 'No documents match your filter.'
                    : structureMapEmptyCopy(documents.length > 0)}
                </li>
              ) : (
                filteredDocuments.map((doc) => {
                  const isRoot = rootIds.includes(doc.id)
                  const selected = doc.id === focusId
                  const levelBadge = structureMapLevelBadge(doc.cascadeLevel)
                  return (
                    <li key={doc.id}>
                      <button
                        type="button"
                        onClick={() => selectFocus(doc.id)}
                        className={
                          selected
                            ? 'w-full rounded-md border border-primary bg-primary/10 px-3 py-2 text-left'
                            : 'w-full rounded-md border border-transparent px-3 py-2 text-left hover:bg-muted/60'
                        }
                        aria-pressed={selected}
                        data-testid={`structure-map-doc-${doc.id}`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-foreground">{doc.title}</span>
                          {levelBadge ? (
                            <Badge
                              variant="outline"
                              data-testid={`structure-map-level-${doc.id}`}
                            >
                              {levelBadge}
                            </Badge>
                          ) : null}
                          {isRoot ? (
                            <Badge variant="secondary" data-testid={`structure-map-root-${doc.id}`}>
                              Root
                            </Badge>
                          ) : null}
                        </div>
                        <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {doc.reference ? (
                            <span className="font-mono">{doc.reference}</span>
                          ) : null}
                          {doc.parentPel ? (
                            <span data-testid={`structure-map-parent-${doc.id}`}>
                              Parent {doc.parentPel}
                            </span>
                          ) : null}
                          {doc.documentType ? <span>{doc.documentType}</span> : null}
                        </div>
                      </button>
                    </li>
                  )
                })
              )}
            </ul>
          </Card>

          <Card className="p-4 space-y-3" data-testid="structure-map-canvas">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Loading cascade aggregate…
              </div>
            ) : null}
            {focusDoc ? (
              <RelationshipsMapView
                documentId={focusDoc.id}
                documentTitle={focusDoc.title}
                documentReference={focusDoc.reference}
                edges={focusEdges}
                labels={labels}
                orientation={orientation}
              />
            ) : (
              <p className="text-sm text-muted-foreground" data-testid="structure-map-empty">
                {documents.length > 0 && bandScopedDocuments.length === 0
                  ? 'No documents in this cascade band. Choose All or another level to explore the estate.'
                  : structureMapEmptyCopy(documents.length > 0)}
              </p>
            )}
            {focusDoc ? (
              <div className="pt-1">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/documents/${focusDoc.id}`} data-testid="structure-map-open-focus">
                    Open {focusDoc.title} in Document Detail
                  </Link>
                </Button>
              </div>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  )
}
