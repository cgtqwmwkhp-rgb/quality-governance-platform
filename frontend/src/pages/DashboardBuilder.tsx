/**
 * Custom Dashboard Builder
 * 
 * Features:
 * - Drag-and-drop widget placement
 * - Widget configuration
 * - Grid-based layout
 * - Save and share dashboards
 */

import { useState } from 'react';
import {
  Plus,
  Save,
  Share2,
  Trash2,
  Settings,
  GripVertical,
  X,
  BarChart3,
  LineChart,
  PieChart,
  TrendingUp,
  Target,
  AlertTriangle,
  CheckCircle,
  Shield,
  Users,
  FileText,
  Clock,
  Activity,
} from 'lucide-react';

interface Widget {
  id: string;
  type: string;
  title: string;
  dataSource: string;
  metric: string;
  x: number;
  y: number;
  w: number;
  h: number;
  config?: Record<string, any>;
}

interface Dashboard {
  id: number;
  name: string;
  description: string;
  widgets: Widget[];
}

const widgetTypes = [
  { type: 'kpi_card', label: 'KPI Card', icon: Target, defaultW: 3, defaultH: 2 },
  { type: 'line_chart', label: 'Line Chart', icon: LineChart, defaultW: 6, defaultH: 4 },
  { type: 'bar_chart', label: 'Bar Chart', icon: BarChart3, defaultW: 6, defaultH: 4 },
  { type: 'pie_chart', label: 'Pie Chart', icon: PieChart, defaultW: 4, defaultH: 4 },
  { type: 'trend_card', label: 'Trend Card', icon: TrendingUp, defaultW: 3, defaultH: 2 },
  { type: 'data_table', label: 'Data Table', icon: FileText, defaultW: 6, defaultH: 4 },
  { type: 'gauge', label: 'Gauge', icon: Activity, defaultW: 3, defaultH: 3 },
  { type: 'timeline', label: 'Timeline', icon: Clock, defaultW: 12, defaultH: 3 },
];

const dataSources = [
  { value: 'incidents', label: 'Incidents', icon: AlertTriangle },
  { value: 'actions', label: 'Actions', icon: CheckCircle },
  { value: 'audits', label: 'Audits', icon: Shield },
  { value: 'risks', label: 'Risks', icon: Target },
  { value: 'compliance', label: 'Compliance', icon: FileText },
  { value: 'training', label: 'Training', icon: Users },
];

const metrics = {
  incidents: ['count', 'open', 'closed', 'by_type', 'by_severity', 'resolution_time'],
  actions: ['count', 'open', 'overdue', 'completion_rate', 'by_status'],
  audits: ['count', 'score', 'by_status', 'findings'],
  risks: ['count', 'by_level', 'mitigated', 'trending'],
  compliance: ['overall_score', 'by_standard', 'gap_count'],
  training: ['completion_rate', 'expiring', 'by_course'],
};

export default function DashboardBuilder() {
  const [dashboard, setDashboard] = useState<Dashboard>({
    id: 1,
    name: 'My Custom Dashboard',
    description: 'Personalized analytics view',
    widgets: [
      { id: 'w1', type: 'kpi_card', title: 'Total Incidents', dataSource: 'incidents', metric: 'count', x: 0, y: 0, w: 3, h: 2 },
      { id: 'w2', type: 'line_chart', title: 'Incident Trend', dataSource: 'incidents', metric: 'count', x: 3, y: 0, w: 6, h: 4 },
      { id: 'w3', type: 'pie_chart', title: 'By Severity', dataSource: 'incidents', metric: 'by_severity', x: 9, y: 0, w: 3, h: 4 },
    ],
  });

  const [selectedWidget, setSelectedWidget] = useState<string | null>(null);
  const [showWidgetPicker, setShowWidgetPicker] = useState(false);
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [editingName, setEditingName] = useState(false);

  const addWidget = (type: string) => {
    const widgetDef = widgetTypes.find(w => w.type === type);
    if (!widgetDef) return;

    const newWidget: Widget = {
      id: `w${Date.now()}`,
      type,
      title: `New ${widgetDef.label}`,
      dataSource: 'incidents',
      metric: 'count',
      x: 0,
      y: Math.max(0, ...dashboard.widgets.map(w => w.y + w.h)),
      w: widgetDef.defaultW,
      h: widgetDef.defaultH,
    };

    setDashboard(prev => ({
      ...prev,
      widgets: [...prev.widgets, newWidget],
    }));
    setSelectedWidget(newWidget.id);
    setShowWidgetPicker(false);
    setShowConfigPanel(true);
  };

  const updateWidget = (widgetId: string, updates: Partial<Widget>) => {
    setDashboard(prev => ({
      ...prev,
      widgets: prev.widgets.map(w => 
        w.id === widgetId ? { ...w, ...updates } : w
      ),
    }));
  };

  const deleteWidget = (widgetId: string) => {
    setDashboard(prev => ({
      ...prev,
      widgets: prev.widgets.filter(w => w.id !== widgetId),
    }));
    setSelectedWidget(null);
    setShowConfigPanel(false);
  };

  const WidgetPreview = ({ widget }: { widget: Widget }) => {
    const widgetDef = widgetTypes.find(w => w.type === widget.type);
    const Icon = widgetDef?.icon || BarChart3;
    const isSelected = selectedWidget === widget.id;

    return (
      <div
        className={`relative bg-card/80 border rounded-xl p-4 cursor-pointer transition-all ${
          isSelected 
            ? 'border-primary ring-2 ring-primary/30' 
            : 'border-border hover:border-border-strong'
        }`}
        style={{
          gridColumn: `span ${widget.w}`,
          gridRow: `span ${widget.h}`,
        }}
        onClick={() => {
          setSelectedWidget(widget.id);
          setShowConfigPanel(true);
        }}
        draggable
      >
        {/* Drag Handle */}
        <div className="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <GripVertical className="w-4 h-4 text-muted-foreground" />
        </div>

        {/* Widget Actions */}
        {isSelected && (
          <div className="absolute top-2 right-2 flex items-center gap-1">
            <button 
              onClick={(e) => { e.stopPropagation(); setShowConfigPanel(true); }}
              className="p-1.5 bg-surface rounded hover:bg-muted text-muted-foreground hover:text-foreground"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); deleteWidget(widget.id); }}
              className="p-1.5 bg-surface rounded hover:bg-destructive text-muted-foreground hover:text-destructive-foreground"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Widget Content Preview */}
        <div className="flex flex-col h-full">
          <div className="flex items-center gap-2 mb-3">
            <Icon className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground truncate">{widget.title}</span>
          </div>
          
          {widget.type === 'kpi_card' && (
            <div className="flex-1 flex flex-col justify-center">
              <div className="text-3xl font-bold text-foreground">47</div>
              <div className="text-sm text-muted-foreground mt-1">Total {widget.metric}</div>
            </div>
          )}

          {widget.type === 'line_chart' && (
            <div className="flex-1 flex items-end gap-1 pb-2">
              {[30, 45, 35, 60, 55, 70, 65, 80, 75, 85].map((h, i) => (
                <div key={i} className="flex-1 bg-primary/30 rounded-t" style={{ height: `${h}%` }} />
              ))}
            </div>
          )}

          {widget.type === 'bar_chart' && (
            <div className="flex-1 flex items-end gap-2 pb-2">
              {[60, 80, 45, 70, 55].map((h, i) => (
                <div key={i} className="flex-1 bg-info rounded-t" style={{ height: `${h}%` }} />
              ))}
            </div>
          )}

          {widget.type === 'pie_chart' && (
            <div className="flex-1 flex items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-gradient-conic from-primary via-info to-purple-500" />
            </div>
          )}

          {widget.type === 'gauge' && (
            <div className="flex-1 flex items-center justify-center">
              <div className="relative w-20 h-10 overflow-hidden">
                <div className="absolute inset-0 rounded-t-full bg-gradient-to-r from-destructive via-warning to-success" />
                <div className="absolute bottom-0 left-1/2 w-1 h-10 bg-foreground origin-bottom -translate-x-1/2 rotate-45" />
              </div>
            </div>
          )}

          {widget.type === 'trend_card' && (
            <div className="flex-1 flex flex-col justify-center">
              <div className="text-2xl font-bold text-foreground">-8.5%</div>
              <div className="flex items-center gap-1 text-success text-sm">
                <TrendingUp className="w-4 h-4" />
                Improving
              </div>
            </div>
          )}

          {widget.type === 'data_table' && (
            <div className="flex-1 space-y-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-4 bg-surface rounded" />
              ))}
            </div>
          )}

          {widget.type === 'timeline' && (
            <div className="flex-1 flex items-center">
              <div className="w-full h-2 bg-surface rounded-full relative">
                {[20, 40, 60, 80].map((pos, i) => (
                  <div key={i} className="absolute w-3 h-3 bg-primary rounded-full top-1/2 -translate-y-1/2" style={{ left: `${pos}%` }} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const selectedWidgetData = dashboard.widgets.find(w => w.id === selectedWidget);

  return (
    <div className="flex h-[calc(100vh-120px)]">
      {/* Main Canvas */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between p-4 bg-card/50 border-b border-border">
          <div className="flex items-center gap-4">
            {editingName ? (
              <input
                type="text"
                value={dashboard.name}
                onChange={(e) => setDashboard(prev => ({ ...prev, name: e.target.value }))}
                onBlur={() => setEditingName(false)}
                onKeyDown={(e) => e.key === 'Enter' && setEditingName(false)}
                className="bg-surface border border-border rounded px-3 py-1 text-foreground text-lg font-semibold focus:ring-2 focus:ring-primary/50"
                autoFocus
              />
            ) : (
              <h1 
                className="text-xl font-bold text-foreground cursor-pointer hover:text-primary transition-colors"
                onClick={() => setEditingName(true)}
              >
                {dashboard.name}
              </h1>
            )}
            <span className="text-sm text-muted-foreground">{dashboard.widgets.length} widgets</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowWidgetPicker(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Widget
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors">
              <Save className="w-4 h-4" />
              Save
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors">
              <Share2 className="w-4 h-4" />
              Share
            </button>
          </div>
        </div>

        {/* Grid Canvas */}
        <div className="flex-1 overflow-auto p-6 bg-slate-900/50">
          <div 
            className="grid gap-4"
            style={{
              gridTemplateColumns: 'repeat(12, 1fr)',
              gridAutoRows: '60px',
            }}
          >
            {dashboard.widgets.map(widget => (
              <WidgetPreview key={widget.id} widget={widget} />
            ))}

            {/* Add Widget Placeholder */}
            {dashboard.widgets.length === 0 && (
              <div 
                className="col-span-12 row-span-4 border-2 border-dashed border-slate-700 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-emerald-500/50 transition-colors"
                onClick={() => setShowWidgetPicker(true)}
              >
                <Plus className="w-12 h-12 text-gray-600 mb-3" />
                <span className="text-gray-400">Click to add your first widget</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Config Panel */}
      {showConfigPanel && selectedWidgetData && (
        <div className="w-80 bg-slate-800 border-l border-slate-700 overflow-y-auto">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="font-semibold text-white">Widget Configuration</h3>
            <button 
              onClick={() => setShowConfigPanel(false)}
              className="text-gray-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-4 space-y-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Title</label>
              <input
                type="text"
                value={selectedWidgetData.title}
                onChange={(e) => updateWidget(selectedWidgetData.id, { title: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Widget Type */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Widget Type</label>
              <select
                value={selectedWidgetData.type}
                onChange={(e) => updateWidget(selectedWidgetData.id, { type: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-emerald-500"
              >
                {widgetTypes.map(type => (
                  <option key={type.type} value={type.type}>{type.label}</option>
                ))}
              </select>
            </div>

            {/* Data Source */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Data Source</label>
              <select
                value={selectedWidgetData.dataSource}
                onChange={(e) => updateWidget(selectedWidgetData.id, { 
                  dataSource: e.target.value,
                  metric: metrics[e.target.value as keyof typeof metrics]?.[0] || 'count'
                })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-emerald-500"
              >
                {dataSources.map(source => (
                  <option key={source.value} value={source.value}>{source.label}</option>
                ))}
              </select>
            </div>

            {/* Metric */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Metric</label>
              <select
                value={selectedWidgetData.metric}
                onChange={(e) => updateWidget(selectedWidgetData.id, { metric: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-emerald-500"
              >
                {(metrics[selectedWidgetData.dataSource as keyof typeof metrics] || ['count']).map(metric => (
                  <option key={metric} value={metric}>{metric.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>

            {/* Size */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Width</label>
                <select
                  value={selectedWidgetData.w}
                  onChange={(e) => updateWidget(selectedWidgetData.id, { w: parseInt(e.target.value) })}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
                >
                  {[3, 4, 6, 8, 12].map(w => (
                    <option key={w} value={w}>{w} cols</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Height</label>
                <select
                  value={selectedWidgetData.h}
                  onChange={(e) => updateWidget(selectedWidgetData.id, { h: parseInt(e.target.value) })}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
                >
                  {[2, 3, 4, 5, 6].map(h => (
                    <option key={h} value={h}>{h} rows</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Delete Button */}
            <div className="pt-4 border-t border-slate-700">
              <button
                onClick={() => deleteWidget(selectedWidgetData.id)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Delete Widget
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Widget Picker Modal */}
      {showWidgetPicker && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-2xl">
            <div className="flex items-center justify-between p-5 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Add Widget</h3>
              <button onClick={() => setShowWidgetPicker(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {widgetTypes.map(type => (
                <button
                  key={type.type}
                  onClick={() => addWidget(type.type)}
                  className="flex flex-col items-center p-4 bg-slate-700/50 hover:bg-emerald-600/20 border border-slate-600 hover:border-emerald-500 rounded-xl transition-all"
                >
                  <type.icon className="w-8 h-8 text-emerald-400 mb-2" />
                  <span className="text-sm text-white">{type.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
