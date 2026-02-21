import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SetupRequiredPanel, isSetupRequired } from '../../../src/components/ui/SetupRequiredPanel';

describe('SetupRequiredPanel', () => {
  const mockResponse = {
    error_class: 'SETUP_REQUIRED' as const,
    setup_required: true as const,
    module: 'planet-mark',
    message: 'Planet Mark module requires initial configuration.',
    next_action: 'Navigate to Admin > Planet Mark to set up reporting years.',
    request_id: 'req-12345',
  };

  it('renders setup panel with module name', () => {
    render(<SetupRequiredPanel response={mockResponse} />);
    expect(screen.getByText('Planet Mark Setup Required')).toBeTruthy();
  });

  it('renders the message', () => {
    render(<SetupRequiredPanel response={mockResponse} />);
    expect(screen.getByText('Planet Mark module requires initial configuration.')).toBeTruthy();
  });

  it('renders the next action', () => {
    render(<SetupRequiredPanel response={mockResponse} />);
    expect(screen.getByText('Navigate to Admin > Planet Mark to set up reporting years.')).toBeTruthy();
  });

  it('renders the request ID', () => {
    render(<SetupRequiredPanel response={mockResponse} />);
    expect(screen.getByText('Request ID: req-12345')).toBeTruthy();
  });

  it('renders refresh button when onRetry is provided', () => {
    const onRetry = vi.fn();
    render(<SetupRequiredPanel response={mockResponse} onRetry={onRetry} />);
    const btn = screen.getByText('Refresh');
    fireEvent.click(btn);
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe('isSetupRequired', () => {
  it('returns true for valid setup required response', () => {
    expect(isSetupRequired({
      error_class: 'SETUP_REQUIRED',
      setup_required: true,
      module: 'test',
      message: 'Test',
    })).toBe(true);
  });

  it('returns false for null', () => {
    expect(isSetupRequired(null)).toBe(false);
  });
});
