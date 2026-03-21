import { describe, it } from 'vitest'
import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../../test/axe-helper'
import { Button } from '../Button'
import { Card, CardHeader, CardTitle, CardContent } from '../Card'
import { Input } from '../Input'
import { Badge } from '../Badge'
import { Label } from '../Label'
import { DataTable, type Column } from '../DataTable'
import { EmptyState } from '../EmptyState'
import { Switch } from '../Switch'

describe('Accessibility — axe-core audit', () => {
  it('Button renders without a11y violations', async () => {
    const { container } = render(<Button>Click me</Button>)
    await expectNoA11yViolations(container)
  })

  it('Button variants render without a11y violations', async () => {
    const { container } = render(
      <div>
        <Button variant="default">Default</Button>
        <Button variant="destructive">Delete</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button disabled>Disabled</Button>
      </div>,
    )
    await expectNoA11yViolations(container)
  })

  it('Card renders without a11y violations', async () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>Test Card</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Card body content</p>
        </CardContent>
      </Card>,
    )
    await expectNoA11yViolations(container)
  })

  it('Input with Label renders without a11y violations', async () => {
    const { container } = render(
      <div>
        <Label htmlFor="email">Email address</Label>
        <Input id="email" type="email" placeholder="you@example.com" />
      </div>,
    )
    await expectNoA11yViolations(container)
  })

  it('Required Label renders without a11y violations', async () => {
    const { container } = render(
      <div>
        <Label htmlFor="name" required>
          Full name
        </Label>
        <Input id="name" type="text" required aria-required="true" />
      </div>,
    )
    await expectNoA11yViolations(container)
  })

  it('Badge renders without a11y violations', async () => {
    const { container } = render(
      <div>
        <Badge>Default</Badge>
        <Badge variant="success">Completed</Badge>
        <Badge variant="destructive">Failed</Badge>
      </div>,
    )
    await expectNoA11yViolations(container)
  })

  it('DataTable renders without a11y violations', async () => {
    interface Row {
      id: number
      name: string
      status: string
    }
    const columns: Column<Row>[] = [
      { key: 'id', header: 'ID' },
      { key: 'name', header: 'Name' },
      { key: 'status', header: 'Status' },
    ]
    const data: Row[] = [
      { id: 1, name: 'Incident A', status: 'Open' },
      { id: 2, name: 'Incident B', status: 'Closed' },
    ]
    const { container } = render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        caption="Recent incidents"
      />,
    )
    await expectNoA11yViolations(container)
  })

  it('DataTable empty state renders without a11y violations', async () => {
    const { container } = render(
      <DataTable
        columns={[{ key: 'x', header: 'Col' }]}
        data={[]}
        keyExtractor={() => '0'}
        emptyMessage="No records found"
      />,
    )
    await expectNoA11yViolations(container)
  })

  it('EmptyState renders without a11y violations', async () => {
    const { container } = render(
      <EmptyState
        title="No incidents"
        description="There are no incidents to display."
      />,
    )
    await expectNoA11yViolations(container)
  })

  it('Switch renders without a11y violations', async () => {
    const { container } = render(
      <div>
        <Label htmlFor="notifications">Enable notifications</Label>
        <Switch id="notifications" aria-label="Enable notifications" />
      </div>,
    )
    await expectNoA11yViolations(container)
  })
})
