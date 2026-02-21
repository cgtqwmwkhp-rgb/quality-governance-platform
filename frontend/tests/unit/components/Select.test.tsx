import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '../../../src/components/ui/Select';

describe('Select', () => {
  it('renders select trigger with placeholder', () => {
    render(
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Choose option" />
        </SelectTrigger>
      </Select>
    );
    expect(screen.getByText('Choose option')).toBeTruthy();
  });

  it('renders select trigger element', () => {
    const { container } = render(
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Pick one" />
        </SelectTrigger>
      </Select>
    );
    expect(container.querySelector('button')).toBeTruthy();
  });

  it('renders with custom className on trigger', () => {
    const { container } = render(
      <Select>
        <SelectTrigger className="custom-class">
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
      </Select>
    );
    expect(container.querySelector('.custom-class')).toBeTruthy();
  });
});
