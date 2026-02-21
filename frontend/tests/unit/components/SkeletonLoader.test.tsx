import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Skeleton, TableSkeleton, CardSkeleton } from '../../../src/components/ui/SkeletonLoader';

describe('Skeleton', () => {
  it('renders with default props', () => {
    const { container } = render(<Skeleton />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper).toBeTruthy();
    expect(wrapper.className).toContain('space-y-3');
    expect(wrapper.children).toHaveLength(3);
  });

  it('renders the specified number of lines', () => {
    const { container } = render(<Skeleton lines={5} />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.children).toHaveLength(5);
  });

  it('applies custom className', () => {
    const { container } = render(<Skeleton className="my-custom" />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('my-custom');
  });

  it('renders last line shorter (w-2/3)', () => {
    const { container } = render(<Skeleton lines={3} />);
    const wrapper = container.firstElementChild as HTMLElement;
    const lastLine = wrapper.children[2] as HTMLElement;
    expect(lastLine.className).toContain('w-2/3');
  });

  it('renders non-last lines full width', () => {
    const { container } = render(<Skeleton lines={3} />);
    const wrapper = container.firstElementChild as HTMLElement;
    const firstLine = wrapper.children[0] as HTMLElement;
    expect(firstLine.className).toContain('w-full');
  });

  it('renders animate-pulse on skeleton bars', () => {
    const { container } = render(<Skeleton lines={2} />);
    const wrapper = container.firstElementChild as HTMLElement;
    const bar = wrapper.children[0] as HTMLElement;
    expect(bar.className).toContain('animate-pulse');
  });

  it('delegates to CardSkeleton when variant is "card"', () => {
    const { container } = render(<Skeleton variant="card" />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.className).toContain('grid');
  });

  it('delegates to TableSkeleton when variant is "table"', () => {
    const { container } = render(<Skeleton variant="table" />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('w-full');
  });
});

describe('TableSkeleton', () => {
  it('renders with default 5 rows and 4 columns', () => {
    const { container } = render(<TableSkeleton />);
    const wrapper = container.firstElementChild as HTMLElement;
    const rowsContainer = wrapper.children[1] as HTMLElement;
    expect(rowsContainer.children).toHaveLength(5);

    const firstRow = rowsContainer.children[0] as HTMLElement;
    expect(firstRow.children).toHaveLength(4);
  });

  it('renders the specified number of rows', () => {
    const { container } = render(<TableSkeleton rows={3} />);
    const wrapper = container.firstElementChild as HTMLElement;
    const rowsContainer = wrapper.children[1] as HTMLElement;
    expect(rowsContainer.children).toHaveLength(3);
  });

  it('renders the specified number of columns', () => {
    const { container } = render(<TableSkeleton columns={6} />);
    const wrapper = container.firstElementChild as HTMLElement;
    const headerRow = wrapper.children[0] as HTMLElement;
    expect(headerRow.children).toHaveLength(6);
  });

  it('applies custom className', () => {
    const { container } = render(<TableSkeleton className="test-class" />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('test-class');
  });

  it('renders header row with border', () => {
    const { container } = render(<TableSkeleton />);
    const wrapper = container.firstElementChild as HTMLElement;
    const header = wrapper.children[0] as HTMLElement;
    expect(header.className).toContain('border-b');
  });
});

describe('CardSkeleton', () => {
  it('renders default 3 cards', () => {
    const { container } = render(<CardSkeleton />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.children).toHaveLength(3);
  });

  it('renders the specified count of cards', () => {
    const { container } = render(<CardSkeleton count={5} />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.children).toHaveLength(5);
  });

  it('uses grid layout', () => {
    const { container } = render(<CardSkeleton />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.className).toContain('grid');
  });

  it('applies custom className', () => {
    const { container } = render(<CardSkeleton className="extra" />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.className).toContain('extra');
  });

  it('cards have rounded border styling', () => {
    const { container } = render(<CardSkeleton count={1} />);
    const grid = container.firstElementChild as HTMLElement;
    const card = grid.children[0] as HTMLElement;
    expect(card.className).toContain('rounded-xl');
    expect(card.className).toContain('border');
  });
});
