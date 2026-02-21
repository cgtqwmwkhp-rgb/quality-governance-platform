import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

import AICopilot from '../../../src/components/copilot/AICopilot';

describe('AICopilot', () => {
  it('renders copilot widget when open', () => {
    render(<AICopilot isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('AI Copilot')).toBeTruthy();
    expect(screen.getByText('Your QHSE Assistant')).toBeTruthy();
  });

  it('renders nothing when closed', () => {
    const { container } = render(<AICopilot isOpen={false} onClose={vi.fn()} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders the input area with placeholder', () => {
    render(<AICopilot isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByPlaceholderText('Ask me anything...')).toBeTruthy();
  });

  it('renders close and minimize buttons', () => {
    render(<AICopilot isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByLabelText('Close copilot')).toBeTruthy();
    expect(screen.getByLabelText('Minimize copilot')).toBeTruthy();
  });
});
