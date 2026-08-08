/**
 * Whole-library Structure map (DG-3) — implements explorer.
 *
 * Flag-gated by `document_graph_structure_map` (master `document_graph` also
 * required for fetches). Reuses DG-1 `RelationshipsMapView` + X-2 GraphCoach /
 * orientation. Never calls Doc Graph the Golden Thread. Never auto-confirms.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { GitBranch, Loader2, ArrowLeft } from 'lucide-react'
import api, { documentGraphApi, getApiErrorMessage } from '../api/client'
import type { DocumentEdge } from '../api/documentGraphClient'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { GraphCoach, GraphOrientationToggle, RelationshipsMapView } from '../components/graph'
import {
  STRUCTURE_MAP_DEFAULT_ORIENTATION,
  buildStructureMapLabels,
  dedupeDocumentEdgesById,
  filterConfirmedImplementsEdges,
  findStructureMapRootIds,
  resolveStructureMapFocusId,
  shouldFetchDocumentStructureMap,
  shouldShowDocumentStructureMap,
  structureMapEmptyCopy,
  type StructureMapDocumentRef,
} from '../components/graph/documentStructureMapHelpers'
import {
  readStoredGraphOrientation,
  resolveGraphOrientation,
  writeStoredGraphOrientation,
  type GraphOrientation,
} from '../components/graph/graphOrientation'

interface LibraryDocumentRow {
  id: number
  title: string
  reference_number?: string | null
  document_type?: string | null
}

interface LibraryDocumentPage {
  items?: LibraryDocumentRow[]
  total?: number
  page?: number
  page_size?: number
  pages?: number
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
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [loadingEdges, setLoadingEdges] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [orientation, setOrientation] = useState<GraphOrientation>(() =>
    resolveGraphOrientation(
      readStoredGraphOrientation('document_structure_map'),
      STRUCTURE_MAP_DEFAULT_ORIENTATION,
    ),
  )

  const rootIds = useMemo(() => findStructureMapRootIds(edges), [edges])
  const focusId = useMemo(
    () => resolveStructureMapFocusId(preferredFocus, documents, rootIds),
    [preferredFocus, documents, rootIds],
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
      ? documents.filter((doc) => {
          const hay = `${doc.title} ${doc.reference ?? ''} ${doc.documentType ?? ''}`.toLowerCase()
          return hay.includes(q)
        })
      : documents
    const rootIdSet = new Set(rootIds)
    return filtered.slice().sort((a, b) => {
      const aIsRoot = rootIdSet.has(a.id)
      const bIsRoot = rootIdSet.has(b.id)
      if (aIsRoot === bIsRoot) return 0
      return aIsRoot ? -1 : 1
    })
  }, [documents, filter, rootIds])

  const loadLibrary = useCallback(async () => {
    if (!shouldFetch) {
      setDocuments([])
      setEdges([])
      setError(null)
      setLoadingDocs(false)
      setLoadingEdges(false)
      return
    }

    setLoadingDocs(true)
    setError(null)
    try {
      const allItems: LibraryDocumentRow[] = []
      const pageSize = 100
      let page = 1
      while (true) {
        const response = await api.get<LibraryDocumentPage | LibraryDocumentRow[]>(
          `/api/v1/documents/?page=${page}&page_size=${pageSize}`,
        )
        const raw = response.data
        const items = Array.isArray(raw) ? raw : (raw.items ?? [])
        allItems.push(...items)

        if (Array.isArray(raw)) break
        const totalPages =
          raw.pages ??
          (raw.total != null
            ? Math.ceil(raw.total / Math.max(1, raw.page_size ?? pageSize))
            : undefined)
        if (totalPages != null ? page >= totalPages : items.length < pageSize) break
        page += 1
      }

      const mapped: StructureMapDocumentRef[] = allItems.map((row) => ({
        id: row.id,
        title: row.title?.trim() || `Document #${row.id}`,
        reference: row.reference_number ?? null,
        documentType: row.document_type ?? null,
      }))
      setDocuments(mapped)
    } catch (err) {
      setDocuments([])
      setError(getApiErrorMessage(err))
    } finally {
      setLoadingDocs(false)
    }
  }, [shouldFetch])

  const loadImplementsEdges = useCallback(
    async (docs: StructureMapDocumentRef[]) => {
      if (!shouldFetch || docs.length === 0) {
        setEdges([])
        setLoadingEdges(false)
        return
      }

      setLoadingEdges(true)
      try {
        const results = await Promise.allSettled(
          docs.map((doc) =>
            documentGraphApi.listEdges(doc.id, {
              edge_type: 'implements',
              status: 'confirmed',
            }),
          ),
        )
        const collected: DocumentEdge[] = []
        const failures: string[] = []
        for (const result of results) {
          if (result.status === 'fulfilled') {
            const items = result.value.data?.items ?? []
            collected.push(...items)
          } else {
            failures.push(getApiErrorMessage(result.reason))
          }
        }
        if (failures.length > 0) {
          setError(
            `Failed to load confirmed implements edges for ${failures.length} of ${results.length} documents: ${failures[0]}`,
          )
        }
        setEdges(dedupeDocumentEdgesById(filterConfirmedImplementsEdges(collected)))
      } catch (err) {
        setEdges([])
        setError(getApiErrorMessage(err))
      } finally {
        setLoadingEdges(false)
      }
    },
    [shouldFetch],
  )

  useEffect(() => {
    void loadLibrary()
  }, [loadLibrary])

  useEffect(() => {
    void loadImplementsEdges(documents)
  }, [documents, loadImplementsEdges])

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
  const loading = loadingDocs || loadingEdges

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
            <Badge variant="outline">Confirmed implements</Badge>
          </div>
          <p className="text-muted-foreground max-w-2xl">
            Whole-library implements explorer — pick a focus document to walk Policy → Procedure →
            SOP on the shared map. Doc Graph spine, not document-control lineage.
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span data-testid="structure-map-doc-count">{documents.length} documents</span>
            <span aria-hidden>·</span>
            <span data-testid="structure-map-edge-count">
              {confirmedCount} confirmed implements
            </span>
            <span aria-hidden>·</span>
            <span data-testid="structure-map-root-count">{rootIds.length} roots</span>
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
          Loading library structure…
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(240px,320px)_1fr]">
          <Card className="p-4 space-y-3" data-testid="structure-map-picker">
            <div className="space-y-1">
              <h2 className="text-sm font-medium text-foreground">Library focus</h2>
              <p className="text-xs text-muted-foreground">
                Roots listed first when known. Search to jump anywhere in the library.
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
                  {filter.trim()
                    ? 'No documents match your filter.'
                    : structureMapEmptyCopy(documents.length > 0)}
                </li>
              ) : (
                filteredDocuments.map((doc) => {
                  const isRoot = rootIds.includes(doc.id)
                  const selected = doc.id === focusId
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
            {loadingEdges ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Loading confirmed implements edges…
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
                {structureMapEmptyCopy(documents.length > 0)}
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
