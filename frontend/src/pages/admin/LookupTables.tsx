import { useTranslation } from 'react-i18next'
import { ClipboardList } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'

const LOOKUP_CATEGORIES = [
  { key: 'incident_types', label: 'Incident Types', count: 6 },
  { key: 'risk_categories', label: 'Risk Categories', count: 8 },
  { key: 'complaint_types', label: 'Complaint Types', count: 5 },
  { key: 'severity_levels', label: 'Severity Levels', count: 4 },
  { key: 'departments', label: 'Departments', count: 0 },
  { key: 'locations', label: 'Locations', count: 0 },
]

export default function LookupTables() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('admin.lookups.title', 'Lookup Tables')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('admin.lookups.subtitle', 'Manage dropdown options and reference data')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {LOOKUP_CATEGORIES.map((cat) => (
          <Card key={cat.key} className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="flex flex-row items-center gap-3 pb-2">
              <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                <ClipboardList className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="font-medium">{cat.label}</p>
                <p className="text-sm text-muted-foreground">
                  {cat.count > 0 ? `${cat.count} items` : 'Not configured'}
                </p>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {t(
                  `admin.lookups.${cat.key}_desc`,
                  `Configure ${cat.label.toLowerCase()} for your organisation`,
                )}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
