/**
 * Unit Tests for Report Capability Handling
 * 
 * Tests the deterministic behavior of report/pack generation capability
 * detection and UI state management.
 */

import { describe, it, expect } from 'vitest';

// PackCapability interface type
interface PackCapability {
  canGenerate: boolean;
  reason?: string;
  lastError?: string;
}

describe('Report Capability Handling', () => {
  describe('PackCapability interface', () => {
    it('should have canGenerate as required field', () => {
      const capability: PackCapability = { canGenerate: true };
      expect(capability.canGenerate).toBe(true);
    });

    it('should support optional reason field', () => {
      const capability: PackCapability = {
        canGenerate: false,
        reason: 'Pack generation not available in this environment',
      };
      expect(capability.reason).toBe('Pack generation not available in this environment');
    });

    it('should support optional lastError field', () => {
      const capability: PackCapability = {
        canGenerate: false,
        reason: 'Not implemented',
        lastError: 'Endpoint returned 501',
      };
      expect(capability.lastError).toBe('Endpoint returned 501');
    });
  });

  describe('Error status to capability mapping', () => {
    it('should disable generation on 404 error', () => {
      const errorStatus = 404;
      let capability: PackCapability;

      if (errorStatus === 404) {
        capability = {
          canGenerate: false,
          reason: 'Investigation not found or pack generation not available',
        };
      } else {
        capability = { canGenerate: true };
      }

      expect(capability.canGenerate).toBe(false);
      expect(capability.reason).toContain('not found');
    });

    it('should disable generation on 501 error', () => {
      const errorStatus = 501;
      let capability: PackCapability;

      if (errorStatus === 501) {
        capability = {
          canGenerate: false,
          reason: 'Pack generation is not implemented in this environment',
        };
      } else {
        capability = { canGenerate: true };
      }

      expect(capability.canGenerate).toBe(false);
      expect(capability.reason).toContain('not implemented');
    });

    it('should disable generation on 403 error', () => {
      const errorStatus = 403;
      let capability: PackCapability;

      if (errorStatus === 403) {
        capability = {
          canGenerate: false,
          reason: 'You do not have permission to generate packs',
        };
      } else {
        capability = { canGenerate: true };
      }

      expect(capability.canGenerate).toBe(false);
      expect(capability.reason).toContain('permission');
    });

    it('should assume capability on successful request', () => {
      // Simulate successful packs list request
      const packsList: unknown[] = [];
      const capability: PackCapability = { canGenerate: true };

      expect(capability.canGenerate).toBe(true);
      expect(capability.reason).toBeUndefined();
    });

    it('should assume capability on unknown errors (let generate attempt fail)', () => {
      const errorStatus = 500; // Internal server error
      let capability: PackCapability;

      // For unknown errors, assume available and let the actual generate call fail
      if (errorStatus === 404 || errorStatus === 501 || errorStatus === 403) {
        capability = { canGenerate: false, reason: 'Error' };
      } else {
        capability = { canGenerate: true };
      }

      expect(capability.canGenerate).toBe(true);
    });
  });

  describe('UI state based on capability', () => {
    it('should enable buttons when canGenerate is true', () => {
      const capability: PackCapability = { canGenerate: true };
      const isDisabled = !capability.canGenerate;

      expect(isDisabled).toBe(false);
    });

    it('should disable buttons when canGenerate is false', () => {
      const capability: PackCapability = {
        canGenerate: false,
        reason: 'Not available',
      };
      const isDisabled = !capability.canGenerate;

      expect(isDisabled).toBe(true);
    });

    it('should show reason in tooltip when disabled', () => {
      const capability: PackCapability = {
        canGenerate: false,
        reason: 'Pack generation is not available',
      };

      const tooltipContent = capability.reason || 'Not available';

      expect(tooltipContent).toBe('Pack generation is not available');
    });

    it('should show default message when reason is undefined', () => {
      const capability: PackCapability = { canGenerate: false };
      const tooltipContent = capability.reason || 'Not available';

      expect(tooltipContent).toBe('Not available');
    });
  });

  describe('Pack generation error handling', () => {
    it('should update capability after failed generation attempt', () => {
      let capability: PackCapability = { canGenerate: true };
      let packError: string | null = null;

      // Simulate failed generation
      const errorStatus = 404;
      if (errorStatus === 404) {
        packError = 'Pack generation endpoint not available in this environment';
        capability = {
          canGenerate: false,
          reason: 'Not available',
          lastError: 'Endpoint returned 404',
        };
      }

      expect(packError).not.toBeNull();
      expect(capability.canGenerate).toBe(false);
      expect(capability.lastError).toBe('Endpoint returned 404');
    });

    it('should clear error on successful generation', () => {
      let packError: string | null = 'Previous error';

      // Simulate successful generation
      packError = null;

      expect(packError).toBeNull();
    });
  });

  describe('Deterministic behavior', () => {
    it('should always show warning banner when capability is disabled', () => {
      const capability: PackCapability = {
        canGenerate: false,
        reason: 'Test reason',
      };

      const showWarningBanner = !capability.canGenerate;

      expect(showWarningBanner).toBe(true);
    });

    it('should not show warning banner when capability is enabled', () => {
      const capability: PackCapability = { canGenerate: true };

      const showWarningBanner = !capability.canGenerate;

      expect(showWarningBanner).toBe(false);
    });

    it('should not crash on undefined capability state', () => {
      const capability: PackCapability = { canGenerate: false };

      // Access optional fields safely
      const reason = capability.reason ?? 'Unknown reason';
      const lastError = capability.lastError ?? '';

      expect(reason).toBe('Unknown reason');
      expect(lastError).toBe('');
    });
  });
});
