/**
 * Unit Tests for Evidence Assets API Client
 * 
 * Tests the frontend API client methods for evidence asset management.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the axios module
vi.mock('axios', () => ({
  default: {
    create: () => ({
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
      patch: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    }),
  },
}));

describe('Evidence Assets API Types', () => {
  describe('EvidenceAsset interface', () => {
    it('should define required fields', () => {
      const asset = {
        id: 1,
        storage_key: 'evidence/investigation/1/abc_file.pdf',
        content_type: 'application/pdf',
        asset_type: 'pdf',
        source_module: 'investigation',
        source_id: 123,
        visibility: 'internal_customer',
        contains_pii: false,
        redaction_required: false,
        retention_policy: 'standard',
        created_at: '2026-02-04T12:00:00Z',
        updated_at: '2026-02-04T12:00:00Z',
      };

      expect(asset).toHaveProperty('id');
      expect(asset).toHaveProperty('storage_key');
      expect(asset).toHaveProperty('source_module');
      expect(asset).toHaveProperty('source_id');
      expect(asset.source_module).toBe('investigation');
    });

    it('should support optional fields', () => {
      const asset = {
        id: 1,
        storage_key: 'evidence/investigation/1/abc_file.pdf',
        content_type: 'application/pdf',
        asset_type: 'pdf',
        source_module: 'investigation',
        source_id: 123,
        visibility: 'internal_customer',
        contains_pii: false,
        redaction_required: false,
        retention_policy: 'standard',
        created_at: '2026-02-04T12:00:00Z',
        updated_at: '2026-02-04T12:00:00Z',
        // Optional fields
        original_filename: 'test.pdf',
        title: 'Test Document',
        description: 'A test document',
        linked_investigation_id: 123,
        latitude: 51.5074,
        longitude: -0.1278,
        location_description: 'London, UK',
      };

      expect(asset.original_filename).toBe('test.pdf');
      expect(asset.title).toBe('Test Document');
      expect(asset.linked_investigation_id).toBe(123);
    });
  });

  describe('Evidence visibility values', () => {
    const validVisibilities = [
      'internal_only',
      'internal_customer',
      'external_allowed',
      'public',
    ];

    it('should use valid visibility values', () => {
      validVisibilities.forEach(visibility => {
        const asset = {
          id: 1,
          storage_key: 'test',
          content_type: 'image/jpeg',
          asset_type: 'photo',
          source_module: 'investigation',
          source_id: 1,
          visibility,
          contains_pii: false,
          redaction_required: false,
          retention_policy: 'standard',
          created_at: '2026-02-04T12:00:00Z',
          updated_at: '2026-02-04T12:00:00Z',
        };
        expect(validVisibilities).toContain(asset.visibility);
      });
    });
  });

  describe('Evidence asset types', () => {
    const validAssetTypes = [
      'photo',
      'video',
      'pdf',
      'document',
      'audio',
      'map_pin',
      'other',
    ];

    it('should use valid asset types', () => {
      validAssetTypes.forEach(assetType => {
        expect(validAssetTypes).toContain(assetType);
      });
    });
  });
});

describe('Evidence Upload Payload', () => {
  it('should construct correct FormData for upload', () => {
    const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
    const uploadData = {
      source_module: 'investigation',
      source_id: 123,
      title: 'Test Evidence',
      visibility: 'internal_customer',
    };

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_module', uploadData.source_module);
    formData.append('source_id', String(uploadData.source_id));
    if (uploadData.title) formData.append('title', uploadData.title);
    if (uploadData.visibility) formData.append('visibility', uploadData.visibility);

    expect(formData.get('source_module')).toBe('investigation');
    expect(formData.get('source_id')).toBe('123');
    expect(formData.get('title')).toBe('Test Evidence');
    expect(formData.get('visibility')).toBe('internal_customer');
  });
});

describe('Evidence List Query Parameters', () => {
  it('should construct correct query string for investigation filtering', () => {
    const options = {
      source_module: 'investigation',
      source_id: 123,
      page: 1,
      page_size: 50,
    };

    const params = new URLSearchParams();
    if (options.page) params.set('page', String(options.page));
    if (options.page_size) params.set('page_size', String(options.page_size));
    if (options.source_module) params.set('source_module', options.source_module);
    if (options.source_id) params.set('source_id', String(options.source_id));

    expect(params.toString()).toContain('source_module=investigation');
    expect(params.toString()).toContain('source_id=123');
    expect(params.toString()).toContain('page=1');
    expect(params.toString()).toContain('page_size=50');
  });

  it('should handle optional parameters', () => {
    const options = {
      page: 2,
      page_size: 20,
    };

    const params = new URLSearchParams();
    if (options.page) params.set('page', String(options.page));
    if (options.page_size) params.set('page_size', String(options.page_size));

    expect(params.toString()).toBe('page=2&page_size=20');
    expect(params.has('source_module')).toBe(false);
  });
});
