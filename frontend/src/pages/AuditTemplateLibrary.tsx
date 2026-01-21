import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  Filter,
  Grid3X3,
  List,
  MoreVertical,
  Star,
  StarOff,
  Copy,
  Trash2,
  Edit,
  Download,
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
  ChevronDown,
  Lock,
  Globe,
  Sparkles,
  Play,
  Archive,
  RotateCcw,
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface AuditTemplate {
  id: string;
  name: string;
  description: string;
  version: string;
  status: 'draft' | 'published' | 'archived';
  category: string;
  subcategory?: string;
  isoStandards: string[];
  questionCount: number;
  sectionCount: number;
  scoringMethod: string;
  passThreshold: number;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  usageCount: number;
  avgScore?: number;
  tags: string[];
  estimatedDuration: number;
  isLocked: boolean;
  isFavorite: boolean;
  isGlobal: boolean;
}

// ============================================================================
// MOCK DATA
// ============================================================================

const MOCK_TEMPLATES: AuditTemplate[] = [
  {
    id: '1',
    name: 'ISO 9001:2015 Full Compliance Audit',
    description: 'Comprehensive audit template covering all clauses of ISO 9001:2015 Quality Management System requirements.',
    version: '3.2.0',
    status: 'published',
    category: 'quality',
    isoStandards: ['iso9001'],
    questionCount: 156,
    sectionCount: 10,
    scoringMethod: 'weighted',
    passThreshold: 85,
    createdAt: '2025-08-15T10:00:00Z',
    updatedAt: '2026-01-10T14:30:00Z',
    createdBy: 'System Admin',
    usageCount: 487,
    avgScore: 87.3,
    tags: ['ISO', 'Quality', 'Certification'],
    estimatedDuration: 180,
    isLocked: true,
    isFavorite: true,
    isGlobal: true,
  },
  {
    id: '2',
    name: 'Vehicle Pre-Departure Inspection',
    description: 'Daily vehicle safety check for fleet vehicles before departure. Covers exterior, interior, and mechanical checks.',
    version: '2.1.0',
    status: 'published',
    category: 'safety',
    isoStandards: ['iso45001'],
    questionCount: 42,
    sectionCount: 5,
    scoringMethod: 'pass_fail',
    passThreshold: 100,
    createdAt: '2025-06-20T09:00:00Z',
    updatedAt: '2026-01-05T11:00:00Z',
    createdBy: 'Fleet Manager',
    usageCount: 2341,
    avgScore: 94.7,
    tags: ['Vehicle', 'Safety', 'Daily'],
    estimatedDuration: 15,
    isLocked: false,
    isFavorite: true,
    isGlobal: false,
  },
  {
    id: '3',
    name: 'Site Environmental Compliance',
    description: 'Environmental impact assessment and compliance check for construction and operational sites.',
    version: '1.5.0',
    status: 'published',
    category: 'environment',
    isoStandards: ['iso14001'],
    questionCount: 78,
    sectionCount: 8,
    scoringMethod: 'weighted',
    passThreshold: 80,
    createdAt: '2025-09-01T08:00:00Z',
    updatedAt: '2025-12-20T16:00:00Z',
    createdBy: 'HSE Director',
    usageCount: 156,
    avgScore: 82.1,
    tags: ['Environment', 'Compliance', 'Site'],
    estimatedDuration: 90,
    isLocked: false,
    isFavorite: false,
    isGlobal: true,
  },
  {
    id: '4',
    name: 'Workplace Safety Walk-Through',
    description: 'Quick safety inspection for office and workshop environments. Identifies immediate hazards and housekeeping issues.',
    version: '1.0.0',
    status: 'published',
    category: 'safety',
    isoStandards: ['iso45001'],
    questionCount: 35,
    sectionCount: 6,
    scoringMethod: 'equal',
    passThreshold: 75,
    createdAt: '2025-11-10T13:00:00Z',
    updatedAt: '2026-01-08T09:00:00Z',
    createdBy: 'Safety Officer',
    usageCount: 892,
    avgScore: 88.5,
    tags: ['Safety', 'Workplace', 'Quick'],
    estimatedDuration: 30,
    isLocked: false,
    isFavorite: false,
    isGlobal: false,
  },
  {
    id: '5',
    name: 'ISO 45001 Health & Safety Management',
    description: 'Full audit template for ISO 45001:2018 Occupational Health and Safety Management System.',
    version: '2.0.0',
    status: 'published',
    category: 'safety',
    isoStandards: ['iso45001'],
    questionCount: 134,
    sectionCount: 10,
    scoringMethod: 'weighted',
    passThreshold: 85,
    createdAt: '2025-07-05T10:00:00Z',
    updatedAt: '2025-12-15T14:00:00Z',
    createdBy: 'System Admin',
    usageCount: 234,
    avgScore: 79.8,
    tags: ['ISO', 'Health', 'Safety', 'Certification'],
    estimatedDuration: 150,
    isLocked: true,
    isFavorite: false,
    isGlobal: true,
  },
  {
    id: '6',
    name: 'New Supplier Qualification',
    description: 'Assessment template for evaluating and qualifying new suppliers before onboarding.',
    version: '1.2.0',
    status: 'draft',
    category: 'quality',
    isoStandards: ['iso9001'],
    questionCount: 52,
    sectionCount: 7,
    scoringMethod: 'points',
    passThreshold: 70,
    createdAt: '2026-01-02T11:00:00Z',
    updatedAt: '2026-01-18T10:00:00Z',
    createdBy: 'Procurement Lead',
    usageCount: 0,
    tags: ['Supplier', 'Quality', 'Onboarding'],
    estimatedDuration: 60,
    isLocked: false,
    isFavorite: false,
    isGlobal: false,
  },
  {
    id: '7',
    name: 'Customer Service Quality Audit',
    description: 'Internal audit for customer service department covering response times, satisfaction, and process adherence.',
    version: '1.0.0',
    status: 'draft',
    category: 'operational',
    isoStandards: [],
    questionCount: 28,
    sectionCount: 4,
    scoringMethod: 'weighted',
    passThreshold: 80,
    createdAt: '2026-01-15T09:00:00Z',
    updatedAt: '2026-01-15T09:00:00Z',
    createdBy: 'CS Manager',
    usageCount: 0,
    tags: ['Customer Service', 'Quality'],
    estimatedDuration: 45,
    isLocked: false,
    isFavorite: false,
    isGlobal: false,
  },
  {
    id: '8',
    name: 'IT Security Assessment (ISO 27001)',
    description: 'Information security management system audit aligned with ISO 27001:2022 requirements.',
    version: '1.1.0',
    status: 'published',
    category: 'security',
    isoStandards: ['iso27001'],
    questionCount: 112,
    sectionCount: 14,
    scoringMethod: 'weighted',
    passThreshold: 90,
    createdAt: '2025-10-20T08:00:00Z',
    updatedAt: '2025-12-28T11:00:00Z',
    createdBy: 'IT Director',
    usageCount: 45,
    avgScore: 76.2,
    tags: ['IT', 'Security', 'ISO', 'Cyber'],
    estimatedDuration: 120,
    isLocked: true,
    isFavorite: true,
    isGlobal: true,
  },
];

const CATEGORIES = [
  { id: 'all', label: 'All Categories', icon: Layers, color: 'slate' },
  { id: 'quality', label: 'Quality', icon: Award, color: 'blue' },
  { id: 'safety', label: 'Health & Safety', icon: HardHat, color: 'orange' },
  { id: 'environment', label: 'Environmental', icon: Leaf, color: 'green' },
  { id: 'security', label: 'Security', icon: Shield, color: 'purple' },
  { id: 'compliance', label: 'Compliance', icon: FileText, color: 'red' },
  { id: 'operational', label: 'Operational', icon: Zap, color: 'yellow' },
];

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AuditTemplateLibrary() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<AuditTemplate[]>(MOCK_TEMPLATES);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [sortBy, setSortBy] = useState<'name' | 'updated' | 'usage' | 'score'>('updated');
  const [activeMenu, setActiveMenu] = useState<string | null>(null);

  // Filter templates
  const filteredTemplates = templates.filter(template => {
    const matchesSearch = 
      template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      template.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;
    const matchesStatus = selectedStatus === 'all' || template.status === selectedStatus;

    return matchesSearch && matchesCategory && matchesStatus;
  });

  // Sort templates
  const sortedTemplates = [...filteredTemplates].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'updated':
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      case 'usage':
        return b.usageCount - a.usageCount;
      case 'score':
        return (b.avgScore || 0) - (a.avgScore || 0);
      default:
        return 0;
    }
  });

  // Toggle favorite
  const toggleFavorite = (id: string) => {
    setTemplates(prev =>
      prev.map(t => t.id === id ? { ...t, isFavorite: !t.isFavorite } : t)
    );
  };

  // Delete template
  const deleteTemplate = (id: string) => {
    if (confirm('Are you sure you want to delete this template?')) {
      setTemplates(prev => prev.filter(t => t.id !== id));
    }
  };

  // Duplicate template
  const duplicateTemplate = (template: AuditTemplate) => {
    const newTemplate: AuditTemplate = {
      ...template,
      id: Math.random().toString(36).substring(2, 11),
      name: `${template.name} (Copy)`,
      status: 'draft',
      version: '1.0.0',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      usageCount: 0,
      avgScore: undefined,
      isLocked: false,
      isFavorite: false,
      isGlobal: false,
    };
    setTemplates(prev => [newTemplate, ...prev]);
  };

  const getCategoryIcon = (categoryId: string) => {
    return CATEGORIES.find(c => c.id === categoryId)?.icon || Layers;
  };

  const getCategoryColor = (categoryId: string) => {
    const colors: Record<string, string> = {
      quality: 'from-blue-500 to-cyan-500',
      safety: 'from-orange-500 to-amber-500',
      environment: 'from-green-500 to-emerald-500',
      security: 'from-purple-500 to-violet-500',
      compliance: 'from-red-500 to-rose-500',
      operational: 'from-yellow-500 to-orange-500',
    };
    return colors[categoryId] || 'from-slate-500 to-slate-600';
  };

  const stats = {
    total: templates.length,
    published: templates.filter(t => t.status === 'published').length,
    draft: templates.filter(t => t.status === 'draft').length,
    totalUsage: templates.reduce((sum, t) => sum + t.usageCount, 0),
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-primary">
            Audit Template Library
          </h1>
          <p className="text-muted-foreground mt-1">Create, manage, and deploy audit templates</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2.5 bg-secondary text-secondary-foreground rounded-lg border border-border hover:bg-surface hover:border-border-strong transition-colors">
            <Upload className="w-4 h-4" />
            Import
          </button>
          <button
            onClick={() => navigate('/audit-templates/new')}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground font-semibold rounded-lg hover:bg-primary-hover transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-0.5"
          >
            <Plus className="w-5 h-5" />
            New Template
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Templates', value: stats.total, icon: Layers, iconBg: 'bg-purple-500/10', iconColor: 'text-purple-500' },
          { label: 'Published', value: stats.published, icon: CheckCircle2, iconBg: 'bg-success/10', iconColor: 'text-success' },
          { label: 'Drafts', value: stats.draft, icon: Edit, iconBg: 'bg-warning/10', iconColor: 'text-warning' },
          { label: 'Total Audits Run', value: stats.totalUsage.toLocaleString(), icon: Play, iconBg: 'bg-info/10', iconColor: 'text-info' },
        ].map((stat, index) => (
          <div
            key={stat.label}
            className="bg-card border border-border rounded-xl p-5 hover:border-border-strong hover:shadow-md transition-all duration-200 group animate-fade-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className={`w-10 h-10 rounded-lg ${stat.iconBg} flex items-center justify-center mb-3`}>
              <stat.icon className={`w-5 h-5 ${stat.iconColor}`} />
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Search, Filters & View Toggle */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search templates by name, description, or tags..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-background border border-border rounded-lg
              text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary
              focus:ring-2 focus:ring-primary/20 transition-all duration-200"
          />
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 lg:pb-0">
          {CATEGORIES.map((category) => (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-all ${
                selectedCategory === category.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-surface border border-border'
              }`}
            >
              <category.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{category.label}</span>
            </button>
          ))}
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-2">
          <div className="flex bg-secondary rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded ${viewMode === 'grid' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded ${viewMode === 'list' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          {/* Sort Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-3 py-2 bg-secondary border border-border rounded-lg text-muted-foreground hover:text-foreground"
            >
              <Filter className="w-4 h-4" />
              <ChevronDown className="w-4 h-4" />
            </button>
            {showFilters && (
              <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-xl shadow-lg z-10 overflow-hidden">
                <div className="p-2">
                  <p className="text-xs text-muted-foreground px-2 mb-2">Sort by</p>
                  {[
                    { id: 'updated', label: 'Last Updated' },
                    { id: 'name', label: 'Name' },
                    { id: 'usage', label: 'Most Used' },
                    { id: 'score', label: 'Highest Score' },
                  ].map((option) => (
                    <button
                      key={option.id}
                      onClick={() => {
                        setSortBy(option.id as typeof sortBy);
                        setShowFilters(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        sortBy === option.id
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-surface'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <div className="border-t border-slate-700 p-2">
                  <p className="text-xs text-slate-500 px-2 mb-2">Status</p>
                  {['all', 'published', 'draft', 'archived'].map((status) => (
                    <button
                      key={status}
                      onClick={() => {
                        setSelectedStatus(status);
                        setShowFilters(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors capitalize ${
                        selectedStatus === status
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-surface'
                      }`}
                    >
                      {status === 'all' ? 'All Statuses' : status}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results Count */}
      <p className="text-sm text-muted-foreground">
        Showing {sortedTemplates.length} of {templates.length} templates
      </p>

      {/* Templates Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {sortedTemplates.map((template, index) => {
            const CategoryIcon = getCategoryIcon(template.category);
            return (
              <div
                key={template.id}
                className="group relative bg-card border border-border rounded-xl overflow-hidden
                  hover:border-border-strong hover:shadow-md transition-all duration-300 animate-fade-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Header Gradient */}
                <div className={`h-2 bg-gradient-to-r ${getCategoryColor(template.category)}`} />

                {/* Content */}
                <div className="p-5">
                  {/* Top Row */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${getCategoryColor(template.category)} flex items-center justify-center`}>
                        <CategoryIcon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <span className={`px-2 py-0.5 text-xs rounded-full border ${
                          template.status === 'published' ? 'bg-success/10 text-success border-success/20' :
                          template.status === 'archived' ? 'bg-secondary text-muted-foreground border-border' :
                          'bg-warning/10 text-warning border-warning/20'
                        }`}>
                          {template.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => toggleFavorite(template.id)}
                        className={`p-1.5 rounded-lg transition-colors ${
                          template.isFavorite ? 'text-warning' : 'text-muted-foreground hover:text-warning'
                        }`}
                      >
                        {template.isFavorite ? <Star className="w-4 h-4 fill-current" /> : <StarOff className="w-4 h-4" />}
                      </button>
                      <div className="relative">
                        <button
                          onClick={() => setActiveMenu(activeMenu === template.id ? null : template.id)}
                          className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-surface"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                        {activeMenu === template.id && (
                          <div className="absolute right-0 mt-1 w-44 bg-card border border-border rounded-xl shadow-lg z-10 overflow-hidden">
                            <button
                              onClick={() => {
                                navigate(`/audit-templates/${template.id}/edit`);
                                setActiveMenu(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface"
                            >
                              <Edit className="w-4 h-4" /> Edit Template
                            </button>
                            <button
                              onClick={() => {
                                duplicateTemplate(template);
                                setActiveMenu(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface"
                            >
                              <Copy className="w-4 h-4" /> Duplicate
                            </button>
                            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface">
                              <Download className="w-4 h-4" /> Export
                            </button>
                            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface">
                              <Archive className="w-4 h-4" /> Archive
                            </button>
                            <div className="border-t border-border" />
                            <button
                              onClick={() => {
                                deleteTemplate(template.id);
                                setActiveMenu(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="w-4 h-4" /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Title & Description */}
                  <h3 className="text-lg font-semibold text-foreground mb-2 line-clamp-2 group-hover:text-primary transition-colors">
                    {template.name}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {template.description}
                  </p>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1 mb-4">
                    {template.isoStandards.map(iso => (
                      <span key={iso} className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full border border-primary/20">
                        {iso.toUpperCase()}
                      </span>
                    ))}
                    {template.isGlobal && (
                      <span className="px-2 py-0.5 bg-info/10 text-info text-xs rounded-full border border-info/20 flex items-center gap-1">
                        <Globe className="w-3 h-3" /> Global
                      </span>
                    )}
                    {template.isLocked && (
                      <span className="px-2 py-0.5 bg-warning/10 text-warning text-xs rounded-full border border-warning/20 flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Locked
                      </span>
                    )}
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="bg-surface rounded-lg p-2">
                      <p className="text-lg font-bold text-foreground">{template.questionCount}</p>
                      <p className="text-xs text-muted-foreground">Questions</p>
                    </div>
                    <div className="bg-surface rounded-lg p-2">
                      <p className="text-lg font-bold text-foreground">{template.estimatedDuration}m</p>
                      <p className="text-xs text-muted-foreground">Duration</p>
                    </div>
                    <div className="bg-surface rounded-lg p-2">
                      <p className={`text-lg font-bold ${
                        (template.avgScore || 0) >= 85 ? 'text-success' :
                        (template.avgScore || 0) >= 70 ? 'text-warning' :
                        'text-muted-foreground'
                      }`}>
                        {template.avgScore ? `${template.avgScore.toFixed(0)}%` : '-'}
                      </p>
                      <p className="text-xs text-muted-foreground">Avg Score</p>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      <span>Updated {new Date(template.updatedAt).toLocaleDateString()}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Play className="w-3 h-3" />
                      <span>{template.usageCount.toLocaleString()} runs</span>
                    </div>
                  </div>
                </div>

                {/* Hover Action */}
                <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-center pb-6">
                  <button
                    onClick={() => navigate(`/audit-templates/${template.id}/edit`)}
                    className="px-6 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary-hover transition-colors"
                  >
                    Open Template
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View */
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Template</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Category</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Questions</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Usage</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Avg Score</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Updated</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sortedTemplates.map((template, index) => {
                const CategoryIcon = getCategoryIcon(template.category);
                return (
                  <tr
                    key={template.id}
                    onClick={() => navigate(`/audit-templates/${template.id}/edit`)}
                    className="hover:bg-surface transition-colors cursor-pointer animate-slide-in"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleFavorite(template.id);
                          }}
                          className={`${template.isFavorite ? 'text-warning' : 'text-muted-foreground hover:text-warning'}`}
                        >
                          {template.isFavorite ? <Star className="w-4 h-4 fill-current" /> : <StarOff className="w-4 h-4" />}
                        </button>
                        <div>
                          <p className="text-sm font-medium text-foreground">{template.name}</p>
                          <p className="text-xs text-muted-foreground truncate max-w-md">{template.description}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <CategoryIcon className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-foreground capitalize">{template.category}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded-full border ${
                        template.status === 'published' ? 'bg-success/10 text-success border-success/20' :
                        template.status === 'archived' ? 'bg-secondary text-muted-foreground border-border' :
                        'bg-warning/10 text-warning border-warning/20'
                      }`}>
                        {template.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground">{template.questionCount}</td>
                    <td className="px-6 py-4 text-sm text-foreground">{template.usageCount.toLocaleString()}</td>
                    <td className="px-6 py-4">
                      {template.avgScore ? (
                        <span className={`text-sm font-medium ${
                          template.avgScore >= 85 ? 'text-success' :
                          template.avgScore >= 70 ? 'text-warning' :
                          'text-destructive'
                        }`}>
                          {template.avgScore.toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {new Date(template.updatedAt).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenu(activeMenu === template.id ? null : template.id);
                        }}
                        className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-surface"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty State */}
      {sortedTemplates.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-surface flex items-center justify-center mx-auto mb-4">
            <FolderOpen className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No templates found</h3>
          <p className="text-muted-foreground mb-6">Try adjusting your search or filters</p>
          <button
            onClick={() => {
              setSearchTerm('');
              setSelectedCategory('all');
              setSelectedStatus('all');
            }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground border border-border rounded-lg hover:bg-surface"
          >
            <RotateCcw className="w-4 h-4" />
            Clear Filters
          </button>
        </div>
      )}

      {/* Quick Start Templates */}
      <div className="mt-12">
        <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          Quick Start Templates
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { title: 'Vehicle Inspection', icon: HardHat, questions: 25, duration: 10 },
            { title: 'Workplace Safety', icon: Shield, questions: 35, duration: 20 },
            { title: 'Quality Check', icon: Award, questions: 20, duration: 15 },
          ].map((quick, idx) => (
            <button
              key={idx}
              onClick={() => navigate('/audit-templates/new')}
              className="flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary hover:shadow-md transition-all group"
            >
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                <quick.icon className="w-6 h-6 text-primary" />
              </div>
              <div className="text-left">
                <p className="font-medium text-foreground">{quick.title}</p>
                <p className="text-xs text-muted-foreground">{quick.questions} questions • ~{quick.duration} min</p>
              </div>
              <Plus className="w-5 h-5 text-muted-foreground ml-auto group-hover:text-primary transition-colors" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
