import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { DataTable, type Column } from '../ui/DataTable'
import { Input } from '../ui/Input'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '../ui/Select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/Tabs'
import { Switch } from '../ui/Switch'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '../ui/DropdownMenu'
import { RadioGroup, RadioGroupItem } from '../ui/RadioGroup'
import { Checkbox } from '../ui/Checkbox'
import { Avatar } from '../ui/Avatar'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '../ui/Tooltip'
import { Textarea } from '../ui/Textarea'
import { ThemeToggle } from '../ui/ThemeToggle'
import { SetupRequiredPanel, type SetupRequiredResponse } from '../ui/SetupRequiredPanel'
import { LoadingSkeleton } from '../ui/LoadingSkeleton'
import { Skeleton } from '../ui/SkeletonLoader'
import { LiveAnnouncerProvider } from '../ui/LiveAnnouncer'
import { ThemeProvider } from '../../contexts/ThemeContext'

describe('DataTable accessibility', () => {
  it('has no a11y violations', async () => {
    const columns: Column<{ id: string; name: string }>[] = [
      { key: 'id', header: 'ID' },
      { key: 'name', header: 'Name' },
    ]
    const data = [{ id: '1', name: 'Alice' }]
    const { container } = render(
      <DataTable columns={columns} data={data} keyExtractor={(r) => r.id} caption="Test table" />,
    )
    await expectNoA11yViolations(container)
  })
})

describe('Input accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Input aria-label="Username" />)
    await expectNoA11yViolations(container)
  })
})

describe('Select accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <Select>
        <SelectTrigger aria-label="Choose option">
          <SelectValue placeholder="Pick one" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
          <SelectItem value="b">Option B</SelectItem>
        </SelectContent>
      </Select>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('Tabs accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('Switch accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Switch aria-label="Toggle notifications" />)
    await expectNoA11yViolations(container)
  })
})

describe('DropdownMenu accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <DropdownMenu>
        <DropdownMenuTrigger aria-label="Open menu">Menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Action 1</DropdownMenuItem>
          <DropdownMenuItem>Action 2</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('RadioGroup accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <RadioGroup aria-label="Colour preference">
        <RadioGroupItem value="red" aria-label="Red" />
        <RadioGroupItem value="blue" aria-label="Blue" />
      </RadioGroup>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('Checkbox accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Checkbox aria-label="Accept terms" />)
    await expectNoA11yViolations(container)
  })
})

describe('Avatar accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Avatar alt="Jane Doe" />)
    await expectNoA11yViolations(container)
  })
})

describe('Tooltip accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button type="button">Hover me</button>
          </TooltipTrigger>
          <TooltipContent>Helpful tip</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('Textarea accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Textarea aria-label="Comments" placeholder="Enter comments" />)
    await expectNoA11yViolations(container)
  })
})

describe('ThemeToggle accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )
    await expectNoA11yViolations(container)
  })
})

describe('SetupRequiredPanel accessibility', () => {
  it('has no a11y violations', async () => {
    const response: SetupRequiredResponse = {
      error_class: 'SETUP_REQUIRED',
      setup_required: true,
      module: 'capa-module',
      message: 'The CAPA module requires initial configuration before use.',
      next_action: 'Contact your administrator to complete setup.',
      request_id: 'req-abc-123',
    }
    const { container } = render(<SetupRequiredPanel response={response} onRetry={() => {}} />)
    await expectNoA11yViolations(container)
  })
})

describe('LoadingSkeleton accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<LoadingSkeleton variant="card" count={2} />)
    await expectNoA11yViolations(container)
  })
})

describe('SkeletonLoader accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(<Skeleton variant="text" lines={3} />)
    await expectNoA11yViolations(container)
  })
})

describe('LiveAnnouncer accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <LiveAnnouncerProvider>
        <p>App content</p>
      </LiveAnnouncerProvider>,
    )
    await expectNoA11yViolations(container)
  })
})
