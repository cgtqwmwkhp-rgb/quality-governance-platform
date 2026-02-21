import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../../src/data/isoStandards', () => ({
  ISO_STANDARDS: [
    { id: 'iso9001', code: 'ISO 9001', name: 'Quality' },
  ],
  getAllClauses: () => [],
  autoTagContent: () => [],
  searchClauses: () => [],
}));

import ISOTagSelector from '../../../src/components/ISOTagSelector';

describe('ISOTagSelector', () => {
  it('renders tag selector with label', () => {
    render(
      <ISOTagSelector
        selectedClauses={[]}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('ISO Clause Tags')).toBeTruthy();
  });

  it('renders add tag button', () => {
    render(
      <ISOTagSelector
        selectedClauses={[]}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Add Tag')).toBeTruthy();
  });

  it('renders with custom label', () => {
    render(
      <ISOTagSelector
        selectedClauses={[]}
        onChange={vi.fn()}
        label="Custom Label"
      />
    );
    expect(screen.getByText('Custom Label')).toBeTruthy();
  });

  it('renders compact variant without error', () => {
    const { container } = render(
      <ISOTagSelector
        selectedClauses={[]}
        onChange={vi.fn()}
        compact
      />
    );
    expect(container).toBeTruthy();
  });
});
