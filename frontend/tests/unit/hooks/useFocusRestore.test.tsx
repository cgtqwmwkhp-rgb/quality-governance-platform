import { renderHook } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useFocusRestore } from '@/hooks/useFocusRestore';

function wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('useFocusRestore', () => {
  it('initializes without error', () => {
    expect(() => {
      renderHook(() => useFocusRestore(), { wrapper });
    }).not.toThrow();
  });
});
