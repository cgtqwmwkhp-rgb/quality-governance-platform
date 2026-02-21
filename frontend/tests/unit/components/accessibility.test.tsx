import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, it, expect } from 'vitest';

import { Button } from '../../../src/components/ui/Button';
import { Input } from '../../../src/components/ui/Input';
import { Textarea } from '../../../src/components/ui/Textarea';
import { Card, CardHeader, CardTitle, CardContent } from '../../../src/components/ui/Card';
import { Badge } from '../../../src/components/ui/Badge';
import { Skeleton, TableSkeleton, CardSkeleton } from '../../../src/components/ui/SkeletonLoader';
import { Avatar } from '../../../src/components/ui/Avatar';

expect.extend(toHaveNoViolations);

describe('Accessibility - axe violations', () => {
  it('Button has no violations', async () => {
    const { container } = render(<Button>Click me</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Button with aria-pressed has no violations', async () => {
    const { container } = render(<Button pressed={true}>Toggle</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Button disabled has aria-disabled', async () => {
    const { container } = render(<Button disabled>Disabled</Button>);
    const button = container.querySelector('button');
    expect(button).toHaveAttribute('aria-disabled', 'true');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Input has no violations', async () => {
    const { container } = render(
      <label>
        Name
        <Input />
      </label>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Input with error has aria-invalid', async () => {
    const { container } = render(
      <label>
        Email
        <Input id="email" error errorMessage="Required field" />
      </label>
    );
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'email-error');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Textarea has no violations', async () => {
    const { container } = render(
      <label>
        Description
        <Textarea />
      </label>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Textarea with error has aria-invalid', async () => {
    const { container } = render(
      <label>
        Notes
        <Textarea id="notes" error errorMessage="Too short" />
      </label>
    );
    const textarea = container.querySelector('textarea');
    expect(textarea).toHaveAttribute('aria-invalid', 'true');
    expect(textarea).toHaveAttribute('aria-describedby', 'notes-error');
  });

  it('Card has no violations', async () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>Test Card</CardTitle>
        </CardHeader>
        <CardContent>Content here</CardContent>
      </Card>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Card renders as article when as="article"', () => {
    const { container } = render(
      <Card as="article">
        <CardContent>Content</CardContent>
      </Card>
    );
    expect(container.querySelector('article')).toBeTruthy();
  });

  it('Badge has role="status"', async () => {
    const { container } = render(<Badge>Active</Badge>);
    const badge = container.querySelector('[role="status"]');
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe('Active');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Skeleton text has loading semantics', async () => {
    const { container } = render(<Skeleton />);
    const status = container.querySelector('[role="status"]');
    expect(status).toBeTruthy();
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-label', 'Loading');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('TableSkeleton has loading semantics', () => {
    const { container } = render(<TableSkeleton />);
    const status = container.querySelector('[role="status"]');
    expect(status).toBeTruthy();
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-label', 'Loading table');
  });

  it('CardSkeleton has loading semantics', () => {
    const { container } = render(<CardSkeleton />);
    const status = container.querySelector('[role="status"]');
    expect(status).toBeTruthy();
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-label', 'Loading cards');
  });

  it('Avatar with image has no role="img"', async () => {
    const { container } = render(<Avatar src="/photo.jpg" alt="Jane Doe" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).not.toHaveAttribute('role');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('Avatar with initials has role="img" and aria-label', async () => {
    const { container } = render(<Avatar alt="Jane Doe" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute('role', 'img');
    expect(wrapper).toHaveAttribute('aria-label', 'Jane Doe');
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
