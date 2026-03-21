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
import { ProgressBar } from '../ProgressBar'
import { Checkbox } from '../Checkbox'
import { RadioGroup, RadioGroupItem } from '../RadioGroup'
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from '../AlertDialog'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '../DropdownMenu'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../Tabs'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '../Select'

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

  it('ProgressBar renders without a11y violations', async () => {
    const { container } = render(<ProgressBar value={50} max={100} aria-label="Progress" />)
    await expectNoA11yViolations(container)
  })

  it('Checkbox with Label renders without a11y violations', async () => {
    const { container } = render(
      <div className="flex items-center gap-2">
        <Checkbox id="terms" />
        <Label htmlFor="terms">Accept terms</Label>
      </div>,
    )
    await expectNoA11yViolations(container)
  })

  it('RadioGroup with RadioGroupItem and labels renders without a11y violations', async () => {
    const { container } = render(
      <RadioGroup defaultValue="a">
        <div className="flex items-center gap-2">
          <RadioGroupItem value="a" id="rg-a" />
          <Label htmlFor="rg-a">Option A</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="b" id="rg-b" />
          <Label htmlFor="rg-b">Option B</Label>
        </div>
      </RadioGroup>,
    )
    await expectNoA11yViolations(container)
  })

  it('AlertDialog renders without a11y violations', async () => {
    const { baseElement } = render(
      <AlertDialog defaultOpen>
        <AlertDialogTrigger asChild>
          <Button type="button">Open dialog</Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogTitle>Confirm action</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. Continue?
          </AlertDialogDescription>
          <AlertDialogAction>Continue</AlertDialogAction>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
        </AlertDialogContent>
      </AlertDialog>,
    )
    await expectNoA11yViolations(baseElement)
  })

  it('DropdownMenu renders without a11y violations', async () => {
    const { baseElement } = render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger asChild>
          <Button type="button">Open menu</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Profile</DropdownMenuItem>
          <DropdownMenuItem>Settings</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    await expectNoA11yViolations(baseElement)
  })

  it('Tabs render without a11y violations', async () => {
    const { container } = render(
      <Tabs defaultValue="one">
        <TabsList>
          <TabsTrigger value="one">Tab one</TabsTrigger>
          <TabsTrigger value="two">Tab two</TabsTrigger>
        </TabsList>
        <TabsContent value="one">Content one</TabsContent>
        <TabsContent value="two">Content two</TabsContent>
      </Tabs>,
    )
    await expectNoA11yViolations(container)
  })

  it('Select renders without a11y violations', async () => {
    const { baseElement } = render(
      <Select defaultOpen>
        <SelectTrigger aria-label="Choose option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="one">One</SelectItem>
          <SelectItem value="two">Two</SelectItem>
        </SelectContent>
      </Select>,
    )
    await expectNoA11yViolations(baseElement)
  })
})
