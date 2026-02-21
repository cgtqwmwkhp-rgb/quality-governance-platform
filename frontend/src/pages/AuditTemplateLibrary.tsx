import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  Search,
  Grid3X3,
  List,
  MoreVertical,
  Copy,
  Edit,
  Upload,
  FolderOpen,
  Clock,
  CheckCircle2,
  Shield,
  Leaf,
  HardHat,
  Zap,
  FileText,
  Award,
  Layers,
  Archive,
  RotateCcw,
  Loader2,
  Filter,
  AlertTriangle,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card, CardContent } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { TableSkeleton } from "../components/ui/SkeletonLoader";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/Dialog";
import { auditsApi, AuditTemplate } from "../api/client";
import { ToastContainer, useToast } from "../components/ui/Toast";

// ============================================================================
// CONSTANTS
// ============================================================================

const CATEGORIES = [
  { id: "all", label: "All Categories", icon: Layers },
  { id: "quality", label: "Quality", icon: Award },
  { id: "safety", label: "Health & Safety", icon: HardHat },
  { id: "environment", label: "Environmental", icon: Leaf },
  { id: "security", label: "Security", icon: Shield },
  { id: "compliance", label: "Compliance", icon: FileText },
  { id: "operational", label: "Operational", icon: Zap },
];

const getCategoryIcon = (categoryId: string) =>
  CATEGORIES.find((c) => c.id === categoryId)?.icon || Layers;

function getDaysRemaining(archivedAt: string): number {
  const archived = new Date(archivedAt);
  const expiry = new Date(archived.getTime() + 30 * 24 * 60 * 60 * 1000);
  const now = new Date();
  return Math.max(
    0,
    Math.ceil((expiry.getTime() - now.getTime()) / (24 * 60 * 60 * 1000)),
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AuditTemplateLibrary() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<AuditTemplate[]>([]);
  const [archivedTemplates, setArchivedTemplates] = useState<AuditTemplate[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [showFilters, setShowFilters] = useState(false);
  const [sortBy, setSortBy] = useState<"name" | "updated">("updated");
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [showArchive, setShowArchive] = useState(false);

  // Two-stage delete state
  const [archiveTarget, setArchiveTarget] = useState<AuditTemplate | null>(
    null,
  );
  const [archiveConfirmStep, setArchiveConfirmStep] = useState<1 | 2>(1);
  const [archiving, setArchiving] = useState(false);

  // Restore state
  const [restoring, setRestoring] = useState<number | null>(null);

  useEffect(() => {
    if (!activeMenu) return;
    const dismiss = () => setActiveMenu(null);
    document.addEventListener("click", dismiss);
    return () => document.removeEventListener("click", dismiss);
  }, [activeMenu]);
  const [cloning, setCloning] = useState<number | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [archivedCount, setArchivedCount] = useState(0);

  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const requestIdRef = useRef(0);

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const loadTemplates = useCallback(async () => {
    const thisRequestId = ++requestIdRef.current;
    try {
      const params: { search?: string; category?: string } = {};
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedCategory !== "all") params.category = selectedCategory;
      const response = await auditsApi.listTemplates(1, 100, params);
      if (thisRequestId !== requestIdRef.current) return;
      setTemplates(response.data.items);
      setTotalCount(response.data.total);
      setError(null);
    } catch (err) {
      if (thisRequestId !== requestIdRef.current) return;
      setError("Failed to load templates.");
      console.error(err);
    } finally {
      if (thisRequestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [debouncedSearch, selectedCategory]);

  const loadArchivedTemplates = useCallback(async () => {
    try {
      setArchiveLoading(true);
      const response = await auditsApi.listArchivedTemplates(1, 100);
      setArchivedTemplates(response.data.items);
      setArchivedCount(response.data.total);
    } catch (err) {
      console.error("Failed to load archived templates:", err);
    } finally {
      setArchiveLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
    loadArchivedTemplates();
  }, [loadTemplates, loadArchivedTemplates]);

  // Two-stage archive: Step 1 shows info, Step 2 requires confirmation
  const handleArchiveStep1 = useCallback((template: AuditTemplate) => {
    setArchiveTarget(template);
    setArchiveConfirmStep(1);
    setActiveMenu(null);
  }, []);

  const handleArchiveConfirm = useCallback(async () => {
    if (!archiveTarget) return;

    if (archiveConfirmStep === 1) {
      setArchiveConfirmStep(2);
      return;
    }

    // Step 2: actually archive
    try {
      setArchiving(true);
      await auditsApi.deleteTemplate(archiveTarget.id);
      setArchiveTarget(null);
      setArchiveConfirmStep(1);
      showToast(
        `"${archiveTarget.name}" moved to archive. Recoverable for 30 days.`,
        "success",
      );
      loadTemplates();
      loadArchivedTemplates();
    } catch (err) {
      showToast("Failed to archive template.", "error");
      console.error(err);
    } finally {
      setArchiving(false);
    }
  }, [
    archiveTarget,
    archiveConfirmStep,
    loadTemplates,
    loadArchivedTemplates,
    showToast,
  ]);

  const handleRestore = useCallback(
    async (template: AuditTemplate) => {
      try {
        setRestoring(template.id);
        await auditsApi.restoreTemplate(template.id);
        showToast(`"${template.name}" restored successfully.`, "success");
        loadTemplates();
        loadArchivedTemplates();
      } catch (err) {
        showToast("Failed to restore template.", "error");
        console.error(err);
      } finally {
        setRestoring(null);
      }
    },
    [loadTemplates, loadArchivedTemplates, showToast],
  );

  const handleClone = useCallback(
    async (template: AuditTemplate) => {
      setCloning(template.id);
      setActiveMenu(null);
      try {
        await auditsApi.cloneTemplate(template.id);
        showToast(`Cloned "${template.name}"`, "success");
        loadTemplates();
      } catch (err) {
        showToast("Failed to clone template.", "error");
        console.error(err);
      } finally {
        setCloning(null);
      }
    },
    [loadTemplates, showToast],
  );

  const sortedTemplates = useMemo(() => {
    return [...templates].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      return (
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
    });
  }, [templates, sortBy]);

  const stats = useMemo(() => {
    const published = templates.filter((t) => t.is_published).length;
    const draft = templates.filter((t) => !t.is_published).length;
    return { total: published + draft, published, draft };
  }, [templates]);

  return (
    <div className="space-y-6 animate-fade-in">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">
            Audit Template Library
          </h1>
          <p className="text-muted-foreground mt-1">
            Create, manage, and deploy audit templates
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant={showArchive ? "default" : "outline"}
            onClick={() => setShowArchive(!showArchive)}
            className="relative"
          >
            <Archive className="w-4 h-4" />
            Archive
            {archivedCount > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs font-bold rounded-full bg-warning text-warning-foreground">
                {archivedCount}
              </span>
            )}
          </Button>
          <Button variant="outline" disabled>
            <Upload className="w-4 h-4" /> Import
          </Button>
          <Button onClick={() => navigate("/audit-templates/new")}>
            <Plus className="w-5 h-5" /> New Template
          </Button>
        </div>
      </div>

      {/* Archive Section */}
      {showArchive && (
        <Card className="border-warning/30 bg-warning/5">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-warning/20 flex items-center justify-center">
                <Archive className="w-5 h-5 text-warning" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Archived Templates
                </h2>
                <p className="text-sm text-muted-foreground">
                  Templates are kept for 30 days before permanent deletion
                </p>
              </div>
            </div>

            {archiveLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            )}

            {!archiveLoading && archivedTemplates.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Archive className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No archived templates</p>
              </div>
            )}

            {!archiveLoading && archivedTemplates.length > 0 && (
              <div className="space-y-3">
                {archivedTemplates.map((template) => {
                  const daysLeft = template.archived_at
                    ? getDaysRemaining(template.archived_at)
                    : 0;
                  const isExpiringSoon = daysLeft <= 7;
                  return (
                    <div
                      key={template.id}
                      className="flex items-center justify-between p-4 rounded-xl bg-background border border-border"
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">
                            {template.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Archived{" "}
                            {template.archived_at
                              ? new Date(
                                  template.archived_at,
                                ).toLocaleDateString()
                              : ""}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <Badge
                          variant={isExpiringSoon ? "destructive" : "warning"}
                          className="whitespace-nowrap"
                        >
                          {isExpiringSoon && (
                            <AlertTriangle className="w-3 h-3 mr-1" />
                          )}
                          {daysLeft} day{daysLeft !== 1 ? "s" : ""} left
                        </Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRestore(template)}
                          disabled={restoring === template.id}
                        >
                          {restoring === template.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RotateCcw className="w-4 h-4" />
                          )}
                          Restore
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          {
            label: "Total Templates",
            value: stats.total,
            icon: Layers,
            iconBg: "bg-primary/10",
            iconColor: "text-primary",
          },
          {
            label: "Published",
            value: stats.published,
            icon: CheckCircle2,
            iconBg: "bg-success/10",
            iconColor: "text-success",
          },
          {
            label: "Drafts",
            value: stats.draft,
            icon: Edit,
            iconBg: "bg-warning/10",
            iconColor: "text-warning",
          },
        ].map((stat, index) => (
          <Card
            key={stat.label}
            hoverable
            className="animate-fade-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <CardContent className="p-5">
              <div
                className={`w-10 h-10 rounded-lg ${stat.iconBg} flex items-center justify-center mb-3`}
              >
                <stat.icon className={`w-5 h-5 ${stat.iconColor}`} />
              </div>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search, Filters & View Toggle */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="relative flex-1">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground"
            aria-hidden="true"
          />
          <label htmlFor="template-search" className="sr-only">
            Search templates
          </label>
          <Input
            id="template-search"
            type="text"
            placeholder="Search templates by name or description..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-12"
          />
        </div>

        <div
          className="flex items-center gap-2 overflow-x-auto pb-2 lg:pb-0"
          role="tablist"
          aria-label="Filter by category"
        >
          {CATEGORIES.map((category) => (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-all min-h-[44px] ${
                selectedCategory === category.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-surface border border-border"
              }`}
              role="tab"
              aria-selected={selectedCategory === category.id}
              aria-label={`Filter by ${category.label}`}
            >
              <category.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{category.label}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div
            className="flex bg-secondary rounded-lg p-1"
            role="radiogroup"
            aria-label="View mode"
          >
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded min-w-[36px] min-h-[36px] ${viewMode === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
              role="radio"
              aria-checked={viewMode === "grid"}
              aria-label="Grid view"
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded min-w-[36px] min-h-[36px] ${viewMode === "list" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
              role="radio"
              aria-checked={viewMode === "list"}
              aria-label="List view"
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          <div className="relative">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
              aria-expanded={showFilters}
              aria-label="Sort options"
            >
              <Filter className="w-4 h-4" />
            </Button>
            {showFilters && (
              <Card className="absolute right-0 mt-2 w-48 z-10">
                <CardContent className="p-2">
                  <p className="text-xs text-muted-foreground px-2 mb-2">
                    Sort by
                  </p>
                  {[
                    { id: "updated" as const, label: "Last Updated" },
                    { id: "name" as const, label: "Name" },
                  ].map((option) => (
                    <button
                      key={option.id}
                      onClick={() => {
                        setSortBy(option.id);
                        setShowFilters(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        sortBy === option.id
                          ? "bg-primary/10 text-primary"
                          : "text-foreground hover:bg-surface"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Results Count */}
      <p className="text-sm text-muted-foreground">
        Showing {sortedTemplates.length} of {totalCount} templates
      </p>

      {/* Loading */}
      {loading && (
        <div className="p-6">
          <TableSkeleton rows={5} columns={4} />
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <Card className="border-destructive/20">
          <CardContent className="p-6 text-center">
            <p className="text-destructive mb-4">{error}</p>
            <Button variant="outline" onClick={loadTemplates}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Templates Grid */}
      {!loading && !error && viewMode === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {sortedTemplates.map((template, index) => {
            const CategoryIcon = getCategoryIcon(template.category || "");
            return (
              <Card
                key={template.id}
                hoverable
                className="group cursor-pointer animate-fade-in"
                style={{ animationDelay: `${index * 50}ms` }}
                onClick={() => navigate(`/audit-templates/${template.id}/edit`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate(`/audit-templates/${template.id}/edit`);
                  }
                }}
                tabIndex={0}
                role="article"
                aria-label={`Template: ${template.name}`}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <CategoryIcon className="w-5 h-5 text-primary" />
                      </div>
                      <Badge
                        variant={template.is_published ? "success" : "warning"}
                      >
                        {template.is_published ? "published" : "draft"}
                      </Badge>
                    </div>
                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenu(
                            activeMenu === String(template.id)
                              ? null
                              : String(template.id),
                          );
                        }}
                        aria-label="Template actions"
                        aria-expanded={activeMenu === String(template.id)}
                      >
                        <MoreVertical className="w-4 h-4" />
                      </Button>
                      {activeMenu === String(template.id) && (
                        <Card className="absolute right-0 mt-1 w-44 z-10">
                          <CardContent className="p-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(
                                  `/audit-templates/${template.id}/edit`,
                                );
                                setActiveMenu(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface rounded-lg"
                            >
                              <Edit className="w-4 h-4" /> Edit
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleClone(template);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface rounded-lg"
                              disabled={cloning === template.id}
                            >
                              {cloning === template.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                              Duplicate
                            </button>
                            <div className="border-t border-border my-1" />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleArchiveStep1(template);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 rounded-lg"
                            >
                              <Archive className="w-4 h-4" /> Archive
                            </button>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </div>

                  <h3 className="text-lg font-semibold text-foreground mb-2 line-clamp-2 group-hover:text-primary transition-colors">
                    {template.name}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {template.description || "No description"}
                  </p>

                  <div className="flex items-center gap-2 flex-wrap mb-4">
                    {template.category && (
                      <Badge variant="default">{template.category}</Badge>
                    )}
                    <Badge variant="secondary">v{template.version}</Badge>
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-border">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      <span>
                        Updated{" "}
                        {new Date(template.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    <Badge variant="secondary">{template.scoring_method}</Badge>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* List View */}
      {!loading && !error && viewMode === "list" && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full" role="table">
              <thead>
                <tr className="border-b border-border">
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    Template
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    Category
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    Status
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    Version
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    Updated
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                  >
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedTemplates.map((template) => {
                  const CategoryIcon = getCategoryIcon(template.category || "");
                  return (
                    <tr
                      key={template.id}
                      onClick={() =>
                        navigate(`/audit-templates/${template.id}/edit`)
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigate(`/audit-templates/${template.id}/edit`);
                        }
                      }}
                      tabIndex={0}
                      className="hover:bg-surface transition-colors cursor-pointer"
                    >
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-foreground">
                          {template.name}
                        </p>
                        <p className="text-xs text-muted-foreground truncate max-w-md">
                          {template.description}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <CategoryIcon className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-foreground capitalize">
                            {template.category || "-"}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge
                          variant={
                            template.is_published ? "success" : "warning"
                          }
                        >
                          {template.is_published ? "published" : "draft"}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-foreground">
                        v{template.version}
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(template.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 relative">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenu(
                              activeMenu === String(template.id)
                                ? null
                                : String(template.id),
                            );
                          }}
                          aria-label="Actions"
                          aria-expanded={activeMenu === String(template.id)}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                        {activeMenu === String(template.id) && (
                          <Card className="absolute right-0 mt-1 w-44 z-10">
                            <CardContent className="p-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate(
                                    `/audit-templates/${template.id}/edit`,
                                  );
                                  setActiveMenu(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface rounded-lg"
                              >
                                <Edit className="w-4 h-4" /> Edit
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleClone(template);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface rounded-lg"
                                disabled={cloning === template.id}
                              >
                                {cloning === template.id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Copy className="w-4 h-4" />
                                )}
                                Duplicate
                              </button>
                              <div className="border-t border-border my-1" />
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleArchiveStep1(template);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 rounded-lg"
                              >
                                <Archive className="w-4 h-4" /> Archive
                              </button>
                            </CardContent>
                          </Card>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Empty State */}
      {!loading && !error && sortedTemplates.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-surface flex items-center justify-center mx-auto mb-4">
            <FolderOpen className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">
            No templates found
          </h3>
          <p className="text-muted-foreground mb-6">
            {searchInput || selectedCategory !== "all"
              ? "Try adjusting your search or filters"
              : "Create your first audit template to get started"}
          </p>
          <div className="flex items-center justify-center gap-3">
            {(searchInput || selectedCategory !== "all") && (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchInput("");
                  setSelectedCategory("all");
                }}
              >
                <RotateCcw className="w-4 h-4" /> Clear Filters
              </Button>
            )}
            <Button onClick={() => navigate("/audit-templates/new")}>
              <Plus className="w-4 h-4" /> New Template
            </Button>
          </div>
        </div>
      )}

      {/* Two-Stage Archive Confirmation Dialog */}
      <Dialog
        open={!!archiveTarget}
        onOpenChange={(open) => {
          if (!open) {
            setArchiveTarget(null);
            setArchiveConfirmStep(1);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {archiveConfirmStep === 1 ? (
                <>
                  <Archive className="w-5 h-5 text-warning" />
                  Archive Template
                </>
              ) : (
                <>
                  <AlertTriangle className="w-5 h-5 text-destructive" />
                  Confirm Archive
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {archiveConfirmStep === 1 ? (
                <>
                  Are you sure you want to archive &quot;{archiveTarget?.name}
                  &quot;?
                  <br />
                  <br />
                  The template will be moved to the archive where it can be
                  <strong> recovered within 30 days</strong>. After 30 days it
                  will be permanently deleted.
                </>
              ) : (
                <>
                  Please confirm that you want to archive &quot;
                  {archiveTarget?.name}&quot;.
                  <br />
                  <br />
                  This template will no longer appear in the active library. You
                  can restore it from the Archive section at any time within 30
                  days.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setArchiveTarget(null);
                setArchiveConfirmStep(1);
              }}
            >
              Cancel
            </Button>
            <Button
              variant={archiveConfirmStep === 1 ? "default" : "destructive"}
              onClick={handleArchiveConfirm}
              disabled={archiving}
            >
              {archiving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              {archiveConfirmStep === 1 ? "Continue" : "Archive Template"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
