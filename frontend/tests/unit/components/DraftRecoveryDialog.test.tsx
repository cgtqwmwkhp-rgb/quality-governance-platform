import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DraftRecoveryDialog } from '../../../src/components/DraftRecoveryDialog';

describe('DraftRecoveryDialog', () => {
  const defaultProps = {
    isOpen: true,
    formType: 'incident',
    savedAt: new Date().toISOString(),
    stepNumber: 2,
    totalSteps: 4,
    onRecover: vi.fn(),
    onDiscard: vi.fn(),
  };

  it('renders dialog when open', () => {
    render(<DraftRecoveryDialog {...defaultProps} />);
    expect(screen.getByText('Resume your Incident Report?')).toBeTruthy();
  });

  it('renders nothing when closed', () => {
    const { container } = render(<DraftRecoveryDialog {...defaultProps} isOpen={false} />);
    expect(container.innerHTML).toBe('');
  });

  it('displays step progress', () => {
    render(<DraftRecoveryDialog {...defaultProps} />);
    expect(screen.getByText('Step 2 of 4')).toBeTruthy();
    expect(screen.getByText('50%')).toBeTruthy();
  });

  it('calls onRecover when Resume Draft is clicked', () => {
    const onRecover = vi.fn();
    render(<DraftRecoveryDialog {...defaultProps} onRecover={onRecover} />);
    fireEvent.click(screen.getByText('Resume Draft'));
    expect(onRecover).toHaveBeenCalledOnce();
  });

  it('calls onDiscard when Start Fresh is clicked', () => {
    const onDiscard = vi.fn();
    render(<DraftRecoveryDialog {...defaultProps} onDiscard={onDiscard} />);
    fireEvent.click(screen.getByText('Start Fresh'));
    expect(onDiscard).toHaveBeenCalledOnce();
  });
});
