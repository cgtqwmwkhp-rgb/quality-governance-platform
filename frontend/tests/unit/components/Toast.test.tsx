import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ToastContainer, useToast, type ToastData } from '../../../src/components/ui/Toast';
import { renderHook } from '@testing-library/react';

describe('ToastContainer', () => {
  const mockDismiss = vi.fn();

  const makeToast = (overrides: Partial<ToastData> = {}): ToastData => ({
    id: 'toast-1',
    message: 'Test message',
    variant: 'success',
    ...overrides,
  });

  it('renders nothing when toasts array is empty', () => {
    const { container } = render(
      <ToastContainer toasts={[]} onDismiss={mockDismiss} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders a toast with the correct message', () => {
    render(
      <ToastContainer
        toasts={[makeToast({ message: 'Operation successful' })]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('Operation successful')).toBeTruthy();
  });

  it('renders with role="alert" for accessibility', () => {
    render(
      <ToastContainer
        toasts={[makeToast()]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByRole('alert')).toBeTruthy();
  });

  it('renders success variant toast', () => {
    render(
      <ToastContainer
        toasts={[makeToast({ variant: 'success', message: 'Success!' })]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('Success!')).toBeTruthy();
  });

  it('renders error variant toast', () => {
    render(
      <ToastContainer
        toasts={[makeToast({ variant: 'error', message: 'Error occurred' })]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('Error occurred')).toBeTruthy();
  });

  it('renders warning variant toast', () => {
    render(
      <ToastContainer
        toasts={[makeToast({ variant: 'warning', message: 'Be careful' })]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('Be careful')).toBeTruthy();
  });

  it('renders info variant toast', () => {
    render(
      <ToastContainer
        toasts={[makeToast({ variant: 'info', message: 'FYI' })]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('FYI')).toBeTruthy();
  });

  it('renders multiple toasts', () => {
    render(
      <ToastContainer
        toasts={[
          makeToast({ id: 't1', message: 'First' }),
          makeToast({ id: 't2', message: 'Second' }),
        ]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByText('First')).toBeTruthy();
    expect(screen.getByText('Second')).toBeTruthy();
  });

  it('has a dismiss button with accessible label', () => {
    render(
      <ToastContainer
        toasts={[makeToast()]}
        onDismiss={mockDismiss}
      />
    );
    expect(screen.getByLabelText('Dismiss notification')).toBeTruthy();
  });
});

describe('useToast', () => {
  it('initializes with empty toasts', () => {
    const { result } = renderHook(() => useToast());
    expect(result.current.toasts).toEqual([]);
  });

  it('adds a toast via show()', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.show('Hello', 'info');
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe('Hello');
    expect(result.current.toasts[0].variant).toBe('info');
  });

  it('defaults to success variant', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.show('Done');
    });

    expect(result.current.toasts[0].variant).toBe('success');
  });

  it('removes a toast via dismiss()', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.show('Remove me');
    });

    const id = result.current.toasts[0].id;

    act(() => {
      result.current.dismiss(id);
    });

    expect(result.current.toasts).toHaveLength(0);
  });
});
