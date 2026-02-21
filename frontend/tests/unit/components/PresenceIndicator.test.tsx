import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import PresenceIndicator from '../../../src/components/realtime/PresenceIndicator';

describe('PresenceIndicator', () => {
  it('renders indicator for online status', () => {
    const { container } = render(<PresenceIndicator status="online" />);
    expect(container.querySelector('.bg-emerald-500')).toBeTruthy();
  });

  it('renders indicator for offline status', () => {
    const { container } = render(<PresenceIndicator status="offline" />);
    expect(container.querySelector('.bg-gray-500')).toBeTruthy();
  });

  it('renders label when showLabel is true', () => {
    render(<PresenceIndicator status="online" showLabel />);
    expect(screen.getByText('Online')).toBeTruthy();
  });

  it('renders with different sizes', () => {
    const { container } = render(<PresenceIndicator status="away" size="lg" />);
    expect(container.querySelector('.w-4')).toBeTruthy();
  });

  it('shows pulse animation for online status', () => {
    const { container } = render(<PresenceIndicator status="online" />);
    expect(container.querySelector('.animate-ping')).toBeTruthy();
  });
});
