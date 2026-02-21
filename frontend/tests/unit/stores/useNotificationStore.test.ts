import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useNotificationStore } from '../../../src/stores/useNotificationStore';

vi.stubGlobal('crypto', {
  randomUUID: () => `test-uuid-${Math.random().toString(36).slice(2, 9)}`,
});

describe('useNotificationStore', () => {
  beforeEach(() => {
    useNotificationStore.setState({ notifications: [], unreadCount: 0 });
  });

  it('should initialize with empty notifications', () => {
    const state = useNotificationStore.getState();
    expect(state.notifications).toEqual([]);
    expect(state.unreadCount).toBe(0);
  });

  it('should add a notification', () => {
    useNotificationStore.getState().addNotification({
      title: 'Test',
      message: 'Hello world',
      type: 'info',
    });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.notifications[0].title).toBe('Test');
    expect(state.notifications[0].message).toBe('Hello world');
    expect(state.notifications[0].type).toBe('info');
    expect(state.notifications[0].read).toBe(false);
    expect(state.unreadCount).toBe(1);
  });

  it('should prepend new notifications', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ title: 'First', message: 'a', type: 'info' });
    store.addNotification({ title: 'Second', message: 'b', type: 'success' });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(2);
    expect(state.notifications[0].title).toBe('Second');
    expect(state.notifications[1].title).toBe('First');
  });

  it('should remove a notification', () => {
    useNotificationStore.getState().addNotification({
      title: 'To Remove',
      message: 'bye',
      type: 'warning',
    });

    const id = useNotificationStore.getState().notifications[0].id;
    useNotificationStore.getState().removeNotification(id);

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });

  it('should clear all notifications', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ title: 'A', message: '1', type: 'info' });
    store.addNotification({ title: 'B', message: '2', type: 'error' });

    useNotificationStore.getState().clearAll();

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });

  it('should mark a notification as read', () => {
    useNotificationStore.getState().addNotification({
      title: 'Unread',
      message: 'read me',
      type: 'info',
    });

    const id = useNotificationStore.getState().notifications[0].id;
    useNotificationStore.getState().markAsRead(id);

    const state = useNotificationStore.getState();
    expect(state.notifications[0].read).toBe(true);
    expect(state.unreadCount).toBe(0);
  });

  it('should mark all notifications as read', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ title: 'A', message: '1', type: 'info' });
    store.addNotification({ title: 'B', message: '2', type: 'info' });

    expect(useNotificationStore.getState().unreadCount).toBe(2);

    useNotificationStore.getState().markAllAsRead();

    const state = useNotificationStore.getState();
    expect(state.unreadCount).toBe(0);
    expect(state.notifications.every((n) => n.read)).toBe(true);
  });

  it('should update unreadCount when removing an unread notification', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ title: 'A', message: '1', type: 'info' });
    store.addNotification({ title: 'B', message: '2', type: 'info' });

    expect(useNotificationStore.getState().unreadCount).toBe(2);

    const id = useNotificationStore.getState().notifications[0].id;
    useNotificationStore.getState().removeNotification(id);

    expect(useNotificationStore.getState().unreadCount).toBe(1);
  });
});
