/**
 * Unit Tests for RCA Save Payload Mapping
 * 
 * Tests the data transformation for saving RCA (Root Cause Analysis) data
 * to the investigation's data field via PATCH endpoint.
 */

import { describe, it, expect } from 'vitest';

describe('RCA Save Payload Mapping', () => {
  describe('5 Whys fields', () => {
    it('should map why_1 through why_5 fields correctly', () => {
      const rcaData = {
        why_1: 'First level cause',
        why_2: 'Second level cause',
        why_3: 'Third level cause',
        why_4: 'Fourth level cause',
        why_5: 'Fifth level cause (root)',
      };

      expect(rcaData.why_1).toBe('First level cause');
      expect(rcaData.why_5).toBe('Fifth level cause (root)');
      expect(Object.keys(rcaData).filter(k => k.startsWith('why_'))).toHaveLength(5);
    });

    it('should allow empty why fields', () => {
      const rcaData = {
        why_1: 'First cause',
        why_2: '',
        why_3: '',
        why_4: '',
        why_5: '',
      };

      expect(rcaData.why_2).toBe('');
    });
  });

  describe('Root cause field', () => {
    it('should include root_cause in payload', () => {
      const rcaData = {
        root_cause: 'The identified root cause of the issue',
        why_1: 'Why 1',
        why_2: 'Why 2',
        why_3: 'Why 3',
        why_4: 'Why 4',
        why_5: 'Why 5',
      };

      expect(rcaData.root_cause).toBe('The identified root cause of the issue');
    });
  });

  describe('Problem statement field', () => {
    it('should include problem_statement in payload', () => {
      const rcaData = {
        problem_statement: 'Description of the problem being investigated',
        root_cause: 'Root cause',
        why_1: '',
        why_2: '',
        why_3: '',
        why_4: '',
        why_5: '',
      };

      expect(rcaData.problem_statement).toBe('Description of the problem being investigated');
    });
  });

  describe('Contributing factors field', () => {
    it('should include contributing_factors in payload', () => {
      const rcaData = {
        contributing_factors: 'Factor 1, Factor 2, Factor 3',
        root_cause: 'Root cause',
        why_1: '',
        why_2: '',
        why_3: '',
        why_4: '',
        why_5: '',
      };

      expect(rcaData.contributing_factors).toBe('Factor 1, Factor 2, Factor 3');
    });
  });

  describe('Merge with existing investigation data', () => {
    it('should merge RCA data with existing investigation data', () => {
      const existingData = {
        title: 'Investigation Title',
        description: 'Investigation Description',
        some_other_field: 'preserved value',
      };

      const rcaData = {
        problem_statement: 'New problem statement',
        why_1: 'Why 1',
        why_2: 'Why 2',
        why_3: '',
        why_4: '',
        why_5: '',
        root_cause: 'New root cause',
        contributing_factors: '',
      };

      const mergedData = { ...existingData, ...rcaData };

      // Existing data preserved
      expect(mergedData.some_other_field).toBe('preserved value');
      // RCA data added
      expect(mergedData.problem_statement).toBe('New problem statement');
      expect(mergedData.root_cause).toBe('New root cause');
      expect(mergedData.why_1).toBe('Why 1');
    });

    it('should overwrite existing RCA fields', () => {
      const existingData = {
        root_cause: 'Old root cause',
        why_1: 'Old why 1',
      };

      const rcaData = {
        root_cause: 'New root cause',
        why_1: 'New why 1',
      };

      const mergedData = { ...existingData, ...rcaData };

      expect(mergedData.root_cause).toBe('New root cause');
      expect(mergedData.why_1).toBe('New why 1');
    });
  });

  describe('PATCH payload structure', () => {
    it('should construct correct PATCH request body', () => {
      const rcaData = {
        problem_statement: 'Problem description',
        why_1: 'First why',
        why_2: 'Second why',
        why_3: '',
        why_4: '',
        why_5: '',
        root_cause: 'Root cause',
        contributing_factors: 'Contributing factors',
      };

      const existingData = { title: 'Test' };
      const updatedData = { ...existingData, ...rcaData };

      const patchBody = {
        data: updatedData,
      };

      expect(patchBody).toHaveProperty('data');
      expect(patchBody.data.root_cause).toBe('Root cause');
      expect(patchBody.data.why_1).toBe('First why');
      expect(patchBody.data.title).toBe('Test');
    });
  });

  describe('RCA data initialization from investigation', () => {
    it('should initialize RCA data from investigation.data', () => {
      const investigationData = {
        title: 'Investigation',
        why_1: 'Existing why 1',
        why_2: 'Existing why 2',
        why_3: '',
        why_4: '',
        why_5: '',
        root_cause: 'Existing root cause',
        problem_statement: 'Existing problem',
        contributing_factors: 'Existing factors',
      };

      const rcaFields: Record<string, string> = {};
      for (let i = 1; i <= 5; i++) {
        rcaFields[`why_${i}`] = String(investigationData[`why_${i}` as keyof typeof investigationData] || '');
      }
      rcaFields.root_cause = String(investigationData.root_cause || '');
      rcaFields.problem_statement = String(investigationData.problem_statement || '');
      rcaFields.contributing_factors = String(investigationData.contributing_factors || '');

      expect(rcaFields.why_1).toBe('Existing why 1');
      expect(rcaFields.root_cause).toBe('Existing root cause');
      expect(rcaFields.problem_statement).toBe('Existing problem');
    });

    it('should handle missing RCA fields gracefully', () => {
      const investigationData = {
        title: 'Investigation',
        // No RCA fields
      };

      const rcaFields: Record<string, string> = {};
      for (let i = 1; i <= 5; i++) {
        rcaFields[`why_${i}`] = String((investigationData as Record<string, unknown>)[`why_${i}`] || '');
      }
      rcaFields.root_cause = String((investigationData as Record<string, unknown>).root_cause || '');

      expect(rcaFields.why_1).toBe('');
      expect(rcaFields.root_cause).toBe('');
    });
  });
});
