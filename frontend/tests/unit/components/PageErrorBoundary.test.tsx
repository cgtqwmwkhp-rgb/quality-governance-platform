import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PageErrorBoundary from '../../../src/components/PageErrorBoundary';

const ThrowingChild = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test explosion');
  }
  return <div>Child content</div>;
};

describe('PageErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when no error occurs', () => {
    render(
      <PageErrorBoundary>
        <div>Safe content</div>
      </PageErrorBoundary>
    );
    expect(screen.getByText('Safe content')).toBeTruthy();
  });

  it('shows error UI when child throws', () => {
    render(
      <PageErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText('Page Error')).toBeTruthy();
    expect(screen.getByText(/encountered an unexpected error/)).toBeTruthy();
  });

  it('displays technical details with the error message', () => {
    render(
      <PageErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText('Technical details')).toBeTruthy();
    expect(screen.getByText('Test explosion')).toBeTruthy();
  });

  it('shows Retry and Go to Dashboard buttons', () => {
    render(
      <PageErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText('Retry')).toBeTruthy();
    expect(screen.getByText('Go to Dashboard')).toBeTruthy();
  });

  it('recovers when Retry is clicked and child no longer throws', () => {
    let shouldThrow = true;
    const ConditionalChild = () => {
      if (shouldThrow) throw new Error('Boom');
      return <div>Child content</div>;
    };

    render(
      <PageErrorBoundary>
        <ConditionalChild />
      </PageErrorBoundary>
    );

    expect(screen.getByText('Page Error')).toBeTruthy();

    shouldThrow = false;
    fireEvent.click(screen.getByText('Retry'));

    expect(screen.getByText('Child content')).toBeTruthy();
  });
});
