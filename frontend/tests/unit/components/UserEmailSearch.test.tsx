import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UserEmailSearch } from '../../../src/components/UserEmailSearch';

vi.mock('../../../src/api/client', () => ({
  usersApi: {
    search: vi.fn().mockResolvedValue({ data: [] }),
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  UserSearchResult: {},
}));

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

describe('UserEmailSearch', () => {
  it('renders with placeholder', () => {
    render(
      <UserEmailSearch value="" onChange={vi.fn()} placeholder="Search users..." />
    );
    expect(screen.getByPlaceholderText('Search users...')).toBeTruthy();
  });

  it('renders with a label', () => {
    render(
      <UserEmailSearch value="" onChange={vi.fn()} label="Assignee" />
    );
    expect(screen.getByText('Assignee')).toBeTruthy();
  });

  it('displays the current value', () => {
    render(
      <UserEmailSearch value="user@test.com" onChange={vi.fn()} />
    );
    expect(screen.getByDisplayValue('user@test.com')).toBeTruthy();
  });

  it('calls onChange when input changes', () => {
    const handleChange = vi.fn();
    render(
      <UserEmailSearch value="" onChange={handleChange} />
    );
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'new@test.com' } });
    expect(handleChange).toHaveBeenCalled();
  });

  it('shows required indicator when required', () => {
    render(
      <UserEmailSearch value="" onChange={vi.fn()} label="Email" required />
    );
    expect(screen.getByText('*')).toBeTruthy();
  });
});
