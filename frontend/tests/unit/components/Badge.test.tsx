import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../../../src/components/ui/Badge';

describe('Badge', () => {
  it('renders with text content', () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('renders with default variant', () => {
    const { container } = render(<Badge>Default</Badge>);
    expect(container.firstChild).toBeTruthy();
    expect(screen.getByText('Default')).toBeTruthy();
  });

  it('renders with destructive variant', () => {
    render(<Badge variant="destructive">Critical</Badge>);
    expect(screen.getByText('Critical')).toBeTruthy();
  });

  it('renders with success variant', () => {
    render(<Badge variant="success">Resolved</Badge>);
    expect(screen.getByText('Resolved')).toBeTruthy();
  });

  it('renders with warning variant', () => {
    render(<Badge variant="warning">Pending</Badge>);
    expect(screen.getByText('Pending')).toBeTruthy();
  });

  it('applies custom className', () => {
    const { container } = render(<Badge className="custom-class">Test</Badge>);
    expect(container.querySelector('.custom-class')).toBeTruthy();
  });
});
