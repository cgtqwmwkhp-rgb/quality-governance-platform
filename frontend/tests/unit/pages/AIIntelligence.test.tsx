import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  aiApi: {
    getPredictions: vi.fn().mockResolvedValue({ data: [] }),
    getInsights: vi.fn().mockResolvedValue({ data: [] }),
    getRecommendations: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/stores/useAppStore', () => ({
  useAppStore: {
    getState: () => ({
      setLoading: vi.fn(),
      setConnectionStatus: vi.fn(),
    }),
  },
}));

vi.mock('../../../src/utils/auth', () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

import AIIntelligence from '../../../src/pages/AIIntelligence';

describe('AIIntelligence', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
