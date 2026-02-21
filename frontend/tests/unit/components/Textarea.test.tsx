import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Textarea } from '../../../src/components/ui/Textarea';

describe('Textarea', () => {
  it('renders a textarea element', () => {
    render(<Textarea placeholder="Enter text" />);
    expect(screen.getByPlaceholderText('Enter text')).toBeTruthy();
  });

  it('accepts and displays a value', () => {
    render(<Textarea value="Hello" onChange={() => {}} />);
    expect(screen.getByDisplayValue('Hello')).toBeTruthy();
  });

  it('calls onChange when value changes', () => {
    const handleChange = vi.fn();
    render(<Textarea onChange={handleChange} placeholder="Type here" />);
    fireEvent.change(screen.getByPlaceholderText('Type here'), { target: { value: 'test' } });
    expect(handleChange).toHaveBeenCalled();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Textarea disabled placeholder="Disabled" />);
    expect(screen.getByPlaceholderText('Disabled')).toHaveProperty('disabled', true);
  });

  it('applies error styling when error prop is set', () => {
    const { container } = render(<Textarea error />);
    expect(container.querySelector('.border-destructive')).toBeTruthy();
  });
});
