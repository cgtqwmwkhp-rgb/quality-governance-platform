import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../../src/api/client', () => ({
  usersApi: {
    search: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

import MentionInput from '../../../src/components/realtime/MentionInput';

describe('MentionInput', () => {
  it('renders input field with default placeholder', () => {
    render(<MentionInput value="" onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText('Type @ to mention someone...')).toBeTruthy();
  });

  it('renders with custom placeholder', () => {
    render(<MentionInput value="" onChange={vi.fn()} placeholder="Write here..." />);
    expect(screen.getByPlaceholderText('Write here...')).toBeTruthy();
  });

  it('renders with provided value', () => {
    render(<MentionInput value="Hello world" onChange={vi.fn()} />);
    expect(screen.getByDisplayValue('Hello world')).toBeTruthy();
  });

  it('renders character count', () => {
    render(<MentionInput value="test" onChange={vi.fn()} maxLength={100} />);
    expect(screen.getByText('4/100')).toBeTruthy();
  });
});
