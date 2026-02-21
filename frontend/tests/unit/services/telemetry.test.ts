import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

import {
  trackExpEvent,
  trackExp001FormOpened,
  trackExp001DraftSaved,
  trackExp001FormSubmitted,
  trackLoginCompleted,
} from '../../../src/services/telemetry';

describe('telemetry service', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('trackExpEvent creates a buffered event in localStorage', () => {
    trackExpEvent('test_event', { formType: 'incident' });
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    expect(buffer.length).toBeGreaterThanOrEqual(1);
    expect(buffer[0].name).toBe('test_event');
  });

  it('trackExpEvent generates a session ID in sessionStorage', () => {
    trackExpEvent('test_session', {});
    expect(sessionStorage.getItem('exp_session_id')).not.toBeNull();
  });

  it('trackExpEvent reuses the same session ID', () => {
    trackExpEvent('first', {});
    const firstId = sessionStorage.getItem('exp_session_id');
    trackExpEvent('second', {});
    const secondId = sessionStorage.getItem('exp_session_id');
    expect(firstId).toBe(secondId);
  });

  it('trackExp001FormOpened emits correct event name', () => {
    trackExp001FormOpened('incident', true, false);
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    const event = buffer.find((e: { name: string }) => e.name === 'exp001_form_opened');
    expect(event).toBeDefined();
    expect(event.dimensions.formType).toBe('incident');
    expect(event.dimensions.flagEnabled).toBe(true);
  });

  it('trackExp001DraftSaved emits correct event', () => {
    trackExp001DraftSaved('near_miss', 2);
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    const event = buffer.find((e: { name: string }) => e.name === 'exp001_draft_saved');
    expect(event).toBeDefined();
    expect(event.dimensions.step).toBe(2);
  });

  it('trackExp001FormSubmitted emits correct event', () => {
    trackExp001FormSubmitted('rta', false, true, 3, false);
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    const event = buffer.find((e: { name: string }) => e.name === 'exp001_form_submitted');
    expect(event).toBeDefined();
    expect(event.dimensions.stepCount).toBe(3);
  });

  it('trackLoginCompleted emits correct dimensions', () => {
    trackLoginCompleted('success', 'fast');
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    const event = buffer.find((e: { name: string }) => e.name === 'login_completed');
    expect(event).toBeDefined();
    expect(event.dimensions.result).toBe('success');
    expect(event.dimensions.durationBucket).toBe('fast');
  });

  it('limits buffer to MAX_BUFFER_SIZE entries', () => {
    for (let i = 0; i < 120; i++) {
      trackExpEvent(`event_${i}`, {});
    }
    const buffer = JSON.parse(localStorage.getItem('exp_telemetry_buffer') || '[]');
    expect(buffer.length).toBeLessThanOrEqual(100);
  });
});
