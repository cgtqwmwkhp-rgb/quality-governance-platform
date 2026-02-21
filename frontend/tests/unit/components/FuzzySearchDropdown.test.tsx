import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FuzzySearchDropdown from '../../../src/components/FuzzySearchDropdown';

const mockOptions = [
  { value: 'opt1', label: 'Option One' },
  { value: 'opt2', label: 'Option Two' },
  { value: 'opt3', label: 'Option Three' },
];

describe('FuzzySearchDropdown', () => {
  it('renders with placeholder', () => {
    render(
      <FuzzySearchDropdown
        options={mockOptions}
        value=""
        onChange={vi.fn()}
        placeholder="Select an option"
      />
    );

    expect(screen.getByText('Select an option')).toBeTruthy();
  });

  it('renders with a label', () => {
    render(
      <FuzzySearchDropdown
        options={mockOptions}
        value=""
        onChange={vi.fn()}
        label="My Dropdown"
      />
    );

    expect(screen.getByText('My Dropdown')).toBeTruthy();
  });

  it('displays the selected option', () => {
    render(
      <FuzzySearchDropdown
        options={mockOptions}
        value="opt1"
        onChange={vi.fn()}
      />
    );

    expect(screen.getByText('Option One')).toBeTruthy();
  });

  it('opens dropdown on click', () => {
    render(
      <FuzzySearchDropdown
        options={mockOptions}
        value=""
        onChange={vi.fn()}
        placeholder="Click me"
      />
    );

    fireEvent.click(screen.getByText('Click me'));
    expect(screen.getByPlaceholderText('Type to search...')).toBeTruthy();
  });

  it('shows options when opened', () => {
    render(
      <FuzzySearchDropdown
        options={mockOptions}
        value=""
        onChange={vi.fn()}
        placeholder="Click me"
      />
    );

    fireEvent.click(screen.getByText('Click me'));
    expect(screen.getByText('Option One')).toBeTruthy();
    expect(screen.getByText('Option Two')).toBeTruthy();
    expect(screen.getByText('Option Three')).toBeTruthy();
  });
});
