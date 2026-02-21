import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/utils/auth', () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

vi.mock('../../../src/stores/useAppStore', () => ({
  useAppStore: {
    getState: () => ({
      setLoading: vi.fn(),
      setConnectionStatus: vi.fn(),
    }),
  },
}));

describe('API client', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('exports the default axios instance', async () => {
    const mod = await import('../../../src/api/client');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default.get).toBe('function');
    expect(typeof mod.default.post).toBe('function');
    expect(typeof mod.default.patch).toBe('function');
    expect(typeof mod.default.delete).toBe('function');
  });

  it('exports authApi with login method', async () => {
    const { authApi } = await import('../../../src/api/client');
    expect(authApi).toBeDefined();
    expect(typeof authApi.login).toBe('function');
  });

  it('exports incidentsApi with CRUD methods', async () => {
    const { incidentsApi } = await import('../../../src/api/client');
    expect(incidentsApi).toBeDefined();
    expect(typeof incidentsApi.list).toBe('function');
    expect(typeof incidentsApi.create).toBe('function');
    expect(typeof incidentsApi.get).toBe('function');
    expect(typeof incidentsApi.update).toBe('function');
  });

  it('exports risksApi', async () => {
    const { risksApi } = await import('../../../src/api/client');
    expect(risksApi).toBeDefined();
    expect(typeof risksApi.list).toBe('function');
    expect(typeof risksApi.create).toBe('function');
  });

  it('exports complaintsApi', async () => {
    const { complaintsApi } = await import('../../../src/api/client');
    expect(complaintsApi).toBeDefined();
    expect(typeof complaintsApi.list).toBe('function');
  });

  it('exports auditsApi with template and run methods', async () => {
    const { auditsApi } = await import('../../../src/api/client');
    expect(auditsApi).toBeDefined();
    expect(typeof auditsApi.listTemplates).toBe('function');
    expect(typeof auditsApi.listRuns).toBe('function');
    expect(typeof auditsApi.createRun).toBe('function');
  });

  it('exports riskRegisterApi', async () => {
    const { riskRegisterApi } = await import('../../../src/api/client');
    expect(riskRegisterApi).toBeDefined();
    expect(typeof riskRegisterApi.list).toBe('function');
    expect(typeof riskRegisterApi.getHeatmap).toBe('function');
    expect(typeof riskRegisterApi.getSummary).toBe('function');
  });

  it('exports investigationsApi', async () => {
    const { investigationsApi } = await import('../../../src/api/client');
    expect(investigationsApi).toBeDefined();
    expect(typeof investigationsApi.list).toBe('function');
    expect(typeof investigationsApi.create).toBe('function');
    expect(typeof investigationsApi.createFromRecord).toBe('function');
  });

  it('exports actionsApi', async () => {
    const { actionsApi } = await import('../../../src/api/client');
    expect(actionsApi).toBeDefined();
    expect(typeof actionsApi.list).toBe('function');
    expect(typeof actionsApi.create).toBe('function');
    expect(typeof actionsApi.update).toBe('function');
  });

  it('exports LoginErrorCode types and classifyLoginError', async () => {
    const { classifyLoginError, LOGIN_ERROR_MESSAGES } = await import('../../../src/api/client');
    expect(typeof classifyLoginError).toBe('function');
    expect(LOGIN_ERROR_MESSAGES).toBeDefined();
    expect(LOGIN_ERROR_MESSAGES.TIMEOUT).toBe('Request timed out. Please try again.');
    expect(LOGIN_ERROR_MESSAGES.UNAUTHORIZED).toBe('Incorrect email or password.');
  });

  it('classifyLoginError returns UNKNOWN for non-axios errors', async () => {
    const { classifyLoginError } = await import('../../../src/api/client');
    expect(classifyLoginError(new Error('random'))).toBe('UNKNOWN');
    expect(classifyLoginError('string error')).toBe('UNKNOWN');
    expect(classifyLoginError(null)).toBe('UNKNOWN');
  });

  it('getDurationBucket returns correct buckets', async () => {
    const { getDurationBucket } = await import('../../../src/api/client');
    expect(getDurationBucket(500)).toBe('fast');
    expect(getDurationBucket(2000)).toBe('normal');
    expect(getDurationBucket(5000)).toBe('slow');
    expect(getDurationBucket(10000)).toBe('very_slow');
    expect(getDurationBucket(20000)).toBe('timeout');
  });

  it('classifyError returns UNKNOWN for non-axios errors', async () => {
    const { classifyError, ErrorClass } = await import('../../../src/api/client');
    expect(classifyError(new Error('test'))).toBe(ErrorClass.UNKNOWN);
  });

  it('getApiErrorMessage returns message for plain errors', async () => {
    const { getApiErrorMessage } = await import('../../../src/api/client');
    expect(getApiErrorMessage(new Error('Something broke'))).toBe('Something broke');
    expect(getApiErrorMessage('not an error')).toBe('An unexpected error occurred');
  });

  it('axios instance has correct baseURL', async () => {
    const api = (await import('../../../src/api/client')).default;
    expect(api.defaults.baseURL).toBe('https://test-api.example.com');
  });

  it('axios instance has correct timeout', async () => {
    const api = (await import('../../../src/api/client')).default;
    expect(api.defaults.timeout).toBe(15000);
  });

  it('axios instance sets JSON content type', async () => {
    const api = (await import('../../../src/api/client')).default;
    expect(api.defaults.headers['Content-Type']).toBe('application/json');
  });
});
