import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  notificationsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    delete: vi.fn(),
  },
}));

import NotificationCenter from '../../../src/components/realtime/NotificationCenter';

describe('NotificationCenter', () => {
  it('renders notification bell button', () => {
    render(
      <BrowserRouter>
        <NotificationCenter />
      </BrowserRouter>
    );
    expect(screen.getByLabelText('Notifications')).toBeTruthy();
  });

  it('renders without crashing with className prop', () => {
    const { container } = render(
      <BrowserRouter>
        <NotificationCenter className="test-class" />
      </BrowserRouter>
    );
    expect(container.querySelector('.test-class')).toBeTruthy();
  });
});
