import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderHook, act } from '@testing-library/react';
import { ToastContainer, useToast, type ToastData } from '../Toast';
import { LiveAnnouncerProvider } from '../LiveAnnouncer';
import type { ReactNode } from 'react';

function Wrapper({ children }: { children: ReactNode }) {
  return <LiveAnnouncerProvider>{children}</LiveAnnouncerProvider>;
}

describe('useToast', () => {
  it('returns show and dismiss functions', () => {
    const { result } = renderHook(() => useToast(), { wrapper: Wrapper });

    expect(typeof result.current.show).toBe('function');
    expect(typeof result.current.dismiss).toBe('function');
    expect(result.current.toasts).toEqual([]);
  });

  it('adds a toast when show is called', () => {
    const { result } = renderHook(() => useToast(), { wrapper: Wrapper });

    act(() => {
      result.current.show('Operation succeeded', 'success');
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe('Operation succeeded');
    expect(result.current.toasts[0].variant).toBe('success');
  });

  it('removes a toast when dismiss is called', () => {
    const { result } = renderHook(() => useToast(), { wrapper: Wrapper });

    act(() => {
      result.current.show('Temp message', 'info');
    });

    const toastId = result.current.toasts[0].id;

    act(() => {
      result.current.dismiss(toastId);
    });

    expect(result.current.toasts).toHaveLength(0);
  });
});

describe('ToastContainer', () => {
  it('renders nothing when toasts array is empty', () => {
    const { container } = render(
      <ToastContainer toasts={[]} onDismiss={() => {}} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders toast messages', () => {
    const toasts: ToastData[] = [
      { id: '1', message: 'Saved!', variant: 'success' },
      { id: '2', message: 'Error occurred', variant: 'error' },
    ];

    render(<ToastContainer toasts={toasts} onDismiss={() => {}} />);

    expect(screen.getByText('Saved!')).toBeInTheDocument();
    expect(screen.getByText('Error occurred')).toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    const toasts: ToastData[] = [
      { id: 'toast-1', message: 'Dismissable', variant: 'info' },
    ];

    render(<ToastContainer toasts={toasts} onDismiss={onDismiss} />);

    const dismissButton = screen.getByLabelText('Dismiss notification');
    await user.click(dismissButton);

    // onDismiss is called after the exit animation timeout (280ms)
    await vi.waitFor(() => {
      expect(onDismiss).toHaveBeenCalledWith('toast-1');
    }, { timeout: 1000 });
  });
});
