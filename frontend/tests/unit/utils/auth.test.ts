import { describe, it, expect, beforeEach } from 'vitest';
import {
  getPlatformToken,
  hasToken,
  clearTokens,
  setAdminToken,
  setPortalToken,
  decodeTokenPayload,
  isTokenExpired,
  getValidPlatformToken,
} from '../../../src/utils/auth';

describe('auth utilities', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  describe('getPlatformToken', () => {
    it('returns null when no token is stored', () => {
      expect(getPlatformToken()).toBeNull();
    });

    it('returns admin token from localStorage', () => {
      localStorage.setItem('access_token', 'admin-jwt');
      expect(getPlatformToken()).toBe('admin-jwt');
    });

    it('returns portal token from sessionStorage when no admin token', () => {
      sessionStorage.setItem('platform_access_token', 'portal-jwt');
      expect(getPlatformToken()).toBe('portal-jwt');
    });

    it('prefers admin token over portal token', () => {
      localStorage.setItem('access_token', 'admin-jwt');
      sessionStorage.setItem('platform_access_token', 'portal-jwt');
      expect(getPlatformToken()).toBe('admin-jwt');
    });
  });

  describe('hasToken', () => {
    it('returns false when no token exists', () => {
      expect(hasToken()).toBe(false);
    });

    it('returns true when admin token exists', () => {
      localStorage.setItem('access_token', 'token');
      expect(hasToken()).toBe(true);
    });
  });

  describe('setAdminToken / setPortalToken', () => {
    it('sets admin token in localStorage', () => {
      setAdminToken('my-admin-token');
      expect(localStorage.getItem('access_token')).toBe('my-admin-token');
    });

    it('sets portal token in sessionStorage', () => {
      setPortalToken('my-portal-token', 'my-refresh');
      expect(sessionStorage.getItem('platform_access_token')).toBe('my-portal-token');
      expect(sessionStorage.getItem('platform_refresh_token')).toBe('my-refresh');
    });
  });

  describe('clearTokens', () => {
    it('clears all tokens from storage', () => {
      localStorage.setItem('access_token', 'admin');
      sessionStorage.setItem('platform_access_token', 'portal');
      sessionStorage.setItem('platform_refresh_token', 'refresh');

      clearTokens();

      expect(localStorage.getItem('access_token')).toBeNull();
      expect(sessionStorage.getItem('platform_access_token')).toBeNull();
      expect(sessionStorage.getItem('platform_refresh_token')).toBeNull();
    });
  });

  describe('decodeTokenPayload', () => {
    it('returns null for invalid tokens', () => {
      expect(decodeTokenPayload('not-a-jwt')).toBeNull();
      expect(decodeTokenPayload('')).toBeNull();
    });

    it('decodes a valid JWT payload', () => {
      const payload = { sub: 'user-1', exp: 9999999999 };
      const encoded = btoa(JSON.stringify(payload));
      const token = `header.${encoded}.signature`;
      const result = decodeTokenPayload(token);
      expect(result).toEqual(payload);
    });
  });

  describe('isTokenExpired', () => {
    it('returns true for invalid tokens', () => {
      expect(isTokenExpired('invalid')).toBe(true);
    });

    it('returns false for a token with far-future expiry', () => {
      const payload = { exp: Math.floor(Date.now() / 1000) + 3600 };
      const encoded = btoa(JSON.stringify(payload));
      const token = `h.${encoded}.s`;
      expect(isTokenExpired(token)).toBe(false);
    });

    it('returns true for an expired token', () => {
      const payload = { exp: Math.floor(Date.now() / 1000) - 3600 };
      const encoded = btoa(JSON.stringify(payload));
      const token = `h.${encoded}.s`;
      expect(isTokenExpired(token)).toBe(true);
    });
  });

  describe('getValidPlatformToken', () => {
    it('returns null when no token exists', () => {
      expect(getValidPlatformToken()).toBeNull();
    });

    it('returns null for expired token', () => {
      const payload = { exp: Math.floor(Date.now() / 1000) - 3600 };
      const encoded = btoa(JSON.stringify(payload));
      localStorage.setItem('access_token', `h.${encoded}.s`);
      expect(getValidPlatformToken()).toBeNull();
    });

    it('returns valid token', () => {
      const payload = { exp: Math.floor(Date.now() / 1000) + 3600 };
      const encoded = btoa(JSON.stringify(payload));
      const token = `h.${encoded}.s`;
      localStorage.setItem('access_token', token);
      expect(getValidPlatformToken()).toBe(token);
    });
  });
});
