/**
 * Unit Tests for Investigation Status Filter Mapping
 * 
 * These tests verify the LOCKED status mapping contract.
 * Changes here require corresponding updates to Playwright E2E.
 */

import { describe, it, expect } from 'vitest';
import {
  STATUS_FILTER_OPTIONS,
  getFilterOption,
  getEnabledFilterOptions,
  getStatusValuesForFilter,
  statusMatchesFilter,
  ALL_STATUS_VALUES,
  InvestigationStatusValue,
} from '../../src/utils/investigationStatusFilter';

describe('Investigation Status Filter Mapping', () => {
  describe('STATUS_FILTER_OPTIONS', () => {
    it('should have 7 filter options', () => {
      expect(STATUS_FILTER_OPTIONS).toHaveLength(7);
    });

    it('should have all required filter IDs', () => {
      const ids = STATUS_FILTER_OPTIONS.map(opt => opt.id);
      expect(ids).toEqual([
        'all',
        'open',
        'in_progress',
        'pending_review',
        'completed',
        'closed',
        'cancelled',
      ]);
    });
  });

  describe('Open filter (LOCKED CONTRACT)', () => {
    it('should include draft and in_progress', () => {
      const openFilter = getFilterOption('open');
      expect(openFilter).toBeDefined();
      expect(openFilter!.values).toEqual(['draft', 'in_progress']);
    });

    it('should match draft status', () => {
      expect(statusMatchesFilter('draft', 'open')).toBe(true);
    });

    it('should match in_progress status', () => {
      expect(statusMatchesFilter('in_progress', 'open')).toBe(true);
    });

    it('should NOT match under_review status', () => {
      expect(statusMatchesFilter('under_review', 'open')).toBe(false);
    });
  });

  describe('Cancelled filter (DISABLED)', () => {
    it('should be disabled', () => {
      const cancelledFilter = getFilterOption('cancelled');
      expect(cancelledFilter).toBeDefined();
      expect(cancelledFilter!.disabled).toBe(true);
    });

    it('should have disabled tooltip', () => {
      const cancelledFilter = getFilterOption('cancelled');
      expect(cancelledFilter!.disabledTooltip).toBe(
        'Cancelled is not supported in the current workflow'
      );
    });

    it('should have empty values (no backend mapping)', () => {
      const cancelledFilter = getFilterOption('cancelled');
      expect(cancelledFilter!.values).toEqual([]);
    });
  });

  describe('All filter', () => {
    it('should have empty values array', () => {
      const allFilter = getFilterOption('all');
      expect(allFilter).toBeDefined();
      expect(allFilter!.values).toEqual([]);
    });

    it('should NOT be disabled', () => {
      const allFilter = getFilterOption('all');
      expect(allFilter!.disabled).toBeFalsy();
    });
  });

  describe('getEnabledFilterOptions', () => {
    it('should return 6 enabled options (excluding cancelled)', () => {
      const enabled = getEnabledFilterOptions();
      expect(enabled).toHaveLength(6);
      expect(enabled.map(o => o.id)).not.toContain('cancelled');
    });
  });

  describe('Status value mapping completeness', () => {
    it('should have all status values mapped in at least one filter', () => {
      const mappedStatuses = new Set<InvestigationStatusValue>();
      STATUS_FILTER_OPTIONS.forEach(opt => {
        opt.values.forEach(v => mappedStatuses.add(v));
      });

      ALL_STATUS_VALUES.forEach(status => {
        expect(mappedStatuses.has(status)).toBe(true);
      });
    });

    it('should not have unmapped values in filters', () => {
      STATUS_FILTER_OPTIONS.forEach(opt => {
        opt.values.forEach(value => {
          expect(ALL_STATUS_VALUES).toContain(value);
        });
      });
    });
  });

  describe('Pending Review maps to under_review', () => {
    it('should map pending_review filter to under_review status', () => {
      const filter = getFilterOption('pending_review');
      expect(filter!.values).toEqual(['under_review']);
    });
  });

  describe('getStatusValuesForFilter', () => {
    it('should return empty array for invalid filter ID', () => {
      expect(getStatusValuesForFilter('nonexistent')).toEqual([]);
    });

    it('should return correct values for each filter', () => {
      expect(getStatusValuesForFilter('all')).toEqual([]);
      expect(getStatusValuesForFilter('open')).toEqual(['draft', 'in_progress']);
      expect(getStatusValuesForFilter('in_progress')).toEqual(['in_progress']);
      expect(getStatusValuesForFilter('pending_review')).toEqual(['under_review']);
      expect(getStatusValuesForFilter('completed')).toEqual(['completed']);
      expect(getStatusValuesForFilter('closed')).toEqual(['closed']);
      expect(getStatusValuesForFilter('cancelled')).toEqual([]);
    });
  });

  describe('statusMatchesFilter', () => {
    it('should correctly match statuses to filters', () => {
      // Test each status against each filter
      const testCases: [InvestigationStatusValue, string, boolean][] = [
        // All filter matches nothing (returns false because it's a special case)
        ['draft', 'all', false],
        ['in_progress', 'all', false],
        
        // Open filter
        ['draft', 'open', true],
        ['in_progress', 'open', true],
        ['under_review', 'open', false],
        ['completed', 'open', false],
        ['closed', 'open', false],
        
        // In Progress filter
        ['draft', 'in_progress', false],
        ['in_progress', 'in_progress', true],
        
        // Pending Review filter
        ['under_review', 'pending_review', true],
        ['in_progress', 'pending_review', false],
        
        // Completed filter
        ['completed', 'completed', true],
        ['closed', 'completed', false],
        
        // Closed filter
        ['closed', 'closed', true],
        ['completed', 'closed', false],
      ];

      testCases.forEach(([status, filterId, expected]) => {
        expect(statusMatchesFilter(status, filterId)).toBe(expected);
      });
    });
  });
});
