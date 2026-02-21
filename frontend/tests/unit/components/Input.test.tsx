import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from '../../../src/components/ui/Input';

describe('Input', () => {
  it('renders an input element', () => {
    render(<Input placeholder="Enter text" />);
    expect(screen.getByPlaceholderText('Enter text')).toBeTruthy();
  });

  it('accepts and displays a value', () => {
    render(<Input value="Hello" onChange={() => {}} />);
    expect(screen.getByDisplayValue('Hello')).toBeTruthy();
  });

  it('calls onChange when value changes', () => {
    const handleChange = vi.fn();
    render(<Input onChange={handleChange} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } });
    expect(handleChange).toHaveBeenCalled();
  });

  it('renders with type="email"', () => {
    const { container } = render(<Input type="email" />);
    expect(container.querySelector('input[type="email"]')).toBeTruthy();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Input disabled placeholder="Disabled" />);
    expect(screen.getByPlaceholderText('Disabled')).toHaveProperty('disabled', true);
  });

  it('applies error styling when error prop is set', () => {
    const { container } = render(<Input error />);
    expect(container.querySelector('.border-destructive')).toBeTruthy();
  });
});
