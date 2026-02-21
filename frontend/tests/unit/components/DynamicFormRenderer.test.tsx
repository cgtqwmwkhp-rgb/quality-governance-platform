import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../../src/hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({ isListening: false, isSupported: false, toggleListening: vi.fn() }),
}));

vi.mock('../../../src/hooks/useGeolocation', () => ({
  useGeolocation: () => ({ isLoading: false, getLocationString: vi.fn(), error: null }),
}));

vi.mock('../../../src/api/client', () => ({
  notificationsApi: { list: vi.fn(), getUnreadCount: vi.fn() },
}));

import DynamicFormRenderer from '../../../src/components/DynamicForm/DynamicFormRenderer';

describe('DynamicFormRenderer', () => {
  const emptyTemplate = {
    id: 1,
    slug: 'test-form',
    name: 'Test Form',
    form_type: 'incident',
    allow_drafts: false,
    is_active: true,
    steps: [
      {
        id: 1,
        name: 'Step 1',
        order: 1,
        description: 'First step',
        fields: [],
      },
    ],
  };

  it('renders with empty config', () => {
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'REF-001' });
    const { container } = render(
      <DynamicFormRenderer template={emptyTemplate as any} onSubmit={onSubmit} />
    );
    expect(container).toBeTruthy();
    expect(screen.getAllByText('Step 1').length).toBeGreaterThan(0);
  });

  it('shows the submit button on last step', () => {
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'REF-001' });
    render(
      <DynamicFormRenderer template={emptyTemplate as any} onSubmit={onSubmit} />
    );
    expect(screen.getByText('Submit')).toBeTruthy();
  });

  it('renders cancel button on first step', () => {
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'REF-001' });
    render(
      <DynamicFormRenderer template={emptyTemplate as any} onSubmit={onSubmit} />
    );
    expect(screen.getByText('Cancel')).toBeTruthy();
  });
});
