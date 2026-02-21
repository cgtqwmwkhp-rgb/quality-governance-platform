import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '../../../src/components/ui/Card';

describe('Card', () => {
  it('renders card with children', () => {
    render(<Card><p>Card content</p></Card>);
    expect(screen.getByText('Card content')).toBeTruthy();
  });

  it('renders all card sub-components', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Body content</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>
    );
    expect(screen.getByText('Title')).toBeTruthy();
    expect(screen.getByText('Description')).toBeTruthy();
    expect(screen.getByText('Body content')).toBeTruthy();
    expect(screen.getByText('Footer')).toBeTruthy();
  });

  it('applies custom className', () => {
    const { container } = render(<Card className="test-class">Content</Card>);
    expect(container.querySelector('.test-class')).toBeTruthy();
  });

  it('applies hoverable styles', () => {
    const { container } = render(<Card hoverable>Hoverable card</Card>);
    expect(container.querySelector('[class*="hover:shadow"]')).toBeTruthy();
  });
});
