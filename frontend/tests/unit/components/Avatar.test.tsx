import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Avatar } from '../../../src/components/ui/Avatar';

describe('Avatar', () => {
  it('renders avatar with fallback initials from alt', () => {
    render(<Avatar alt="John Doe" />);
    expect(screen.getByText('JD')).toBeTruthy();
  });

  it('renders avatar with custom fallback', () => {
    render(<Avatar fallback="AB" />);
    expect(screen.getByText('AB')).toBeTruthy();
  });

  it('renders avatar with image when src is provided', () => {
    const { container } = render(<Avatar src="https://example.com/avatar.png" alt="User" />);
    const img = container.querySelector('img');
    expect(img).toBeTruthy();
    expect(img?.getAttribute('src')).toBe('https://example.com/avatar.png');
  });

  it('renders with different sizes', () => {
    const { container: sm } = render(<Avatar size="sm" fallback="A" />);
    expect(sm.querySelector('.h-8')).toBeTruthy();

    const { container: lg } = render(<Avatar size="lg" fallback="B" />);
    expect(lg.querySelector('.h-12')).toBeTruthy();
  });

  it('renders fallback "?" when no alt or fallback given', () => {
    render(<Avatar />);
    expect(screen.getByText('?')).toBeTruthy();
  });
});
