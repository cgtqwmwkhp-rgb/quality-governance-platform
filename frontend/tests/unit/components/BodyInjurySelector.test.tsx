import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import BodyInjurySelector from '../../../src/components/BodyInjurySelector';

describe('BodyInjurySelector', () => {
  it('renders the front/back view toggle', () => {
    render(<BodyInjurySelector injuries={[]} onChange={vi.fn()} />);
    expect(screen.getByText('Front View')).toBeTruthy();
    expect(screen.getByText('Back View')).toBeTruthy();
  });

  it('renders the instruction text', () => {
    render(<BodyInjurySelector injuries={[]} onChange={vi.fn()} />);
    expect(screen.getByText('Tap a body part to add an injury')).toBeTruthy();
  });

  it('renders the SVG body diagram', () => {
    const { container } = render(<BodyInjurySelector injuries={[]} onChange={vi.fn()} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('shows injuries summary when injuries are provided', () => {
    const injuries = [
      { regionId: 'chest', regionLabel: 'Chest', injuryType: 'bruise', injuryLabel: 'Bruise / Contusion', view: 'front' as const },
    ];
    render(<BodyInjurySelector injuries={injuries} onChange={vi.fn()} />);
    expect(screen.getByText('Injuries Selected (1)')).toBeTruthy();
    expect(screen.getByText('Chest')).toBeTruthy();
  });

  it('does not show injuries summary when no injuries', () => {
    render(<BodyInjurySelector injuries={[]} onChange={vi.fn()} />);
    expect(screen.queryByText(/Injuries Selected/)).toBeNull();
  });
});
