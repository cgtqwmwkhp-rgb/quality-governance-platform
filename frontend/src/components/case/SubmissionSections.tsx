import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { SubmissionSection } from '../../helpers/caseSubmission'

interface SubmissionSectionsProps {
  sections: SubmissionSection[]
  emptyMessage: string
}

export function SubmissionSections({ sections, emptyMessage }: SubmissionSectionsProps) {
  const visibleSections = sections.filter((section) =>
    section.fields.some((field) => field.value && field.value !== 'Not provided'),
  )

  if (visibleSections.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">{emptyMessage}</CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {visibleSections.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle className="text-base">{section.title}</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {section.fields.map((field) => (
              <div key={`${section.title}-${field.label}`}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {field.label}
                </p>
                <p className="text-sm text-foreground mt-1 whitespace-pre-wrap">{field.value}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
