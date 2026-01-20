import { useEffect, useState } from 'react'
import { Search, BookOpen, ChevronRight, ChevronDown, CheckCircle2, Circle, AlertCircle, Shield, Award, Loader2 } from 'lucide-react'
import { standardsApi, Standard, Clause } from '../api/client'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { cn } from "../helpers/utils"

interface ExpandedState {
  [key: number]: boolean
}

const ISO_ICONS: Record<string, string> = {
  'ISO9001': '🏆',
  'ISO14001': '🌍',
  'ISO27001': '🔐',
  'ISO45001': '⛑️',
  'ISO22000': '🍽️',
}

export default function Standards() {
  const [standards, setStandards] = useState<Standard[]>([])
  const [selectedStandard, setSelectedStandard] = useState<Standard | null>(null)
  const [clauses, setClauses] = useState<Clause[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingClauses, setLoadingClauses] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [expanded, setExpanded] = useState<ExpandedState>({})

  useEffect(() => {
    loadStandards()
  }, [])

  const loadStandards = async () => {
    try {
      const response = await standardsApi.list(1, 50)
      setStandards(response.data.items || [])
    } catch (err) {
      console.error('Failed to load standards:', err)
      setStandards([])
    } finally {
      setLoading(false)
    }
  }

  const loadClauses = async (standard: Standard) => {
    setLoadingClauses(true)
    setSelectedStandard(standard)
    try {
      const response = await standardsApi.get(standard.id)
      setClauses(response.data.clauses || [])
    } catch (err) {
      console.error('Failed to load clauses:', err)
      setClauses([])
    } finally {
      setLoadingClauses(false)
    }
  }

  const toggleExpanded = (id: number) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  // Mock compliance data for demo
  const mockCompliance: Record<string, number> = {
    'ISO9001': 87,
    'ISO14001': 72,
    'ISO27001': 94,
    'ISO45001': 81,
  }

  const filteredStandards = standards.filter(
    s => s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
         s.code.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Group clauses by level
  const topLevelClauses = clauses.filter(c => c.level === 1)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Standards & Compliance</h1>
          <p className="text-muted-foreground mt-1">ISO standards library, clauses & implementation tracking</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Standards List */}
        <div className="xl:col-span-1 space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search standards..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Standards Cards */}
          <div className="space-y-3">
            {filteredStandards.length === 0 ? (
              <Card className="p-8 text-center">
                <BookOpen className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <p className="text-muted-foreground">No standards found</p>
              </Card>
            ) : (
              filteredStandards.map((standard) => {
                const compliance = mockCompliance[standard.code] || 0
                const isSelected = selectedStandard?.id === standard.id
                
                return (
                  <Card
                    key={standard.id}
                    hoverable
                    onClick={() => loadClauses(standard)}
                    className={cn(
                      "p-5 cursor-pointer",
                      isSelected && "border-primary shadow-lg"
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-2xl flex-shrink-0">
                        {ISO_ICONS[standard.code] || '📋'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-primary">{standard.code}</span>
                          {standard.is_active && (
                            <Badge variant="success" className="text-[10px]">
                              Active
                            </Badge>
                          )}
                        </div>
                        <h3 className="font-semibold text-foreground truncate">{standard.name}</h3>
                        <p className="text-xs text-muted-foreground mt-1">Version {standard.version}</p>
                      </div>
                    </div>

                    {/* Compliance Bar */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-muted-foreground">Compliance</span>
                        <span className={cn(
                          "font-bold",
                          compliance >= 90 ? "text-success" :
                          compliance >= 70 ? "text-warning" : "text-destructive"
                        )}>
                          {compliance}%
                        </span>
                      </div>
                      <div className="h-2 bg-surface rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            "h-full transition-all duration-500 rounded-full",
                            compliance >= 90 ? "bg-success" :
                            compliance >= 70 ? "bg-warning" : "bg-destructive"
                          )}
                          style={{ width: `${compliance}%` }}
                        />
                      </div>
                    </div>
                  </Card>
                )
              })
            )}
          </div>
        </div>

        {/* Clauses Panel */}
        <div className="xl:col-span-2">
          {!selectedStandard ? (
            <Card className="p-12 text-center h-full flex flex-col items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-6">
                <Award className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">Select a Standard</h3>
              <p className="text-muted-foreground max-w-md">
                Choose a standard from the list to view its clauses, controls, and implementation status.
              </p>
            </Card>
          ) : loadingClauses ? (
            <Card className="p-12 text-center">
              <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto" />
            </Card>
          ) : (
            <Card className="overflow-hidden">
              {/* Header */}
              <div className="p-6 border-b border-border bg-primary/5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center text-xl">
                    {ISO_ICONS[selectedStandard.code] || '📋'}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-foreground">{selectedStandard.name}</h2>
                    <p className="text-sm text-muted-foreground">{selectedStandard.full_name}</p>
                  </div>
                </div>
              </div>

              {/* Clauses Tree */}
              <div className="p-4 max-h-[600px] overflow-y-auto">
                {topLevelClauses.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <BookOpen className="w-10 h-10 mx-auto mb-3 text-muted-foreground/50" />
                    <p>No clauses defined for this standard</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {topLevelClauses.map((clause, index) => {
                      const isExpanded = expanded[clause.id]
                      const subClauses = clauses.filter(c => c.level === 2)
                      const hasChildren = subClauses.length > 0
                      
                      // Mock implementation status
                      const mockStatus = ['implemented', 'partial', 'planned', 'not_implemented'][index % 4]
                      
                      return (
                        <div key={clause.id}>
                          <div 
                            onClick={() => hasChildren && toggleExpanded(clause.id)}
                            className={cn(
                              "flex items-center gap-3 p-4 rounded-xl transition-all duration-200",
                              hasChildren && "cursor-pointer hover:bg-surface"
                            )}
                          >
                            {hasChildren ? (
                              isExpanded ? (
                                <ChevronDown className="w-5 h-5 text-primary" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-muted-foreground" />
                              )
                            ) : (
                              <div className="w-5" />
                            )}
                            
                            <div className={cn(
                              "w-8 h-8 rounded-lg flex items-center justify-center",
                              mockStatus === 'implemented' ? 'bg-success/10' :
                              mockStatus === 'partial' ? 'bg-warning/10' :
                              mockStatus === 'planned' ? 'bg-info/10' : 'bg-destructive/10'
                            )}>
                              {mockStatus === 'implemented' ? (
                                <CheckCircle2 className="w-4 h-4 text-success" />
                              ) : mockStatus === 'partial' ? (
                                <Circle className="w-4 h-4 text-warning" />
                              ) : mockStatus === 'planned' ? (
                                <Circle className="w-4 h-4 text-info" />
                              ) : (
                                <AlertCircle className="w-4 h-4 text-destructive" />
                              )}
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm text-primary">{clause.clause_number}</span>
                                <h4 className="font-medium text-foreground truncate">{clause.title}</h4>
                              </div>
                            </div>

                            <Badge variant={
                              mockStatus === 'implemented' ? 'resolved' :
                              mockStatus === 'partial' ? 'in-progress' :
                              mockStatus === 'planned' ? 'submitted' : 'destructive'
                            }>
                              {mockStatus.replace('_', ' ')}
                            </Badge>
                          </div>

                          {/* Sub-clauses */}
                          {isExpanded && hasChildren && (
                            <div className="ml-8 pl-4 border-l-2 border-border space-y-1 mt-2">
                              {subClauses.slice(0, 5).map((subClause) => (
                                <div 
                                  key={subClause.id}
                                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface transition-colors"
                                >
                                  <Shield className="w-4 h-4 text-muted-foreground" />
                                  <span className="font-mono text-xs text-primary">{subClause.clause_number}</span>
                                  <span className="text-sm text-foreground truncate">{subClause.title}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
