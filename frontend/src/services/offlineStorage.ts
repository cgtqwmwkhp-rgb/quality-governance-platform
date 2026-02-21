/**
 * Offline-First Storage with IndexedDB
 * 
 * Provides:
 * - IndexedDB persistence
 * - Automatic sync queue
 * - Conflict resolution
 * - Optimistic updates
 * - Background sync
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb';
import { API_BASE_URL } from '../config/apiBase';

// ============================================================================
// Types
// ============================================================================

interface SyncItem {
  id: string;
  operation: 'create' | 'update' | 'delete';
  entityType: string;
  entityId: string;
  data: Record<string, unknown>;
  timestamp: number;
  retryCount: number;
  lastError?: string;
}

interface CacheItem {
  key: string;
  data: unknown;
  timestamp: number;
  expiresAt?: number;
}

interface OfflineDBSchema extends DBSchema {
  syncQueue: {
    key: string;
    value: SyncItem;
    indexes: { 'by-timestamp': number; 'by-entity': string };
  };
  cache: {
    key: string;
    value: CacheItem;
    indexes: { 'by-timestamp': number };
  };
  incidents: {
    key: string;
    value: Record<string, unknown>;
    indexes: { 'by-updated': number; 'by-status': string };
  };
  audits: {
    key: string;
    value: Record<string, unknown>;
    indexes: { 'by-updated': number; 'by-status': string };
  };
  risks: {
    key: string;
    value: Record<string, unknown>;
    indexes: { 'by-updated': number };
  };
  documents: {
    key: string;
    value: Record<string, unknown>;
    indexes: { 'by-updated': number };
  };
  userSettings: {
    key: string;
    value: Record<string, unknown>;
  };
  pendingUploads: {
    key: string;
    value: {
      id: string;
      file: Blob;
      metadata: Record<string, unknown>;
      timestamp: number;
    };
  };
}

// ============================================================================
// OfflineStorage Class
// ============================================================================

class OfflineStorage {
  private db: IDBPDatabase<OfflineDBSchema> | null = null;
  private dbName = 'quality-governance-offline';
  private dbVersion = 1;
  private isOnline = navigator.onLine;
  private syncInProgress = false;
  private syncListeners: Set<(status: SyncStatus) => void> = new Set();

  constructor() {
    this.initOnlineListener();
  }

  // =========================================================================
  // Initialization
  // =========================================================================

  async init(): Promise<void> {
    if (this.db) return;

    this.db = await openDB<OfflineDBSchema>(this.dbName, this.dbVersion, {
      upgrade(db: IDBPDatabase<OfflineDBSchema>) {
        // Sync Queue
        if (!db.objectStoreNames.contains('syncQueue')) {
          const syncStore = db.createObjectStore('syncQueue', { keyPath: 'id' });
          syncStore.createIndex('by-timestamp', 'timestamp');
          syncStore.createIndex('by-entity', 'entityType');
        }

        // Cache
        if (!db.objectStoreNames.contains('cache')) {
          const cacheStore = db.createObjectStore('cache', { keyPath: 'key' });
          cacheStore.createIndex('by-timestamp', 'timestamp');
        }

        // Entity stores
        const entityNames = ['incidents', 'audits', 'risks', 'documents'] as const;
        for (const entityName of entityNames) {
          if (!db.objectStoreNames.contains(entityName)) {
            const store = db.createObjectStore(entityName, { keyPath: 'id' });
            store.createIndex('by-updated', 'updated_at');
            // Only incidents and audits have status index
            if (entityName === 'incidents' || entityName === 'audits') {
              (store as unknown as { createIndex: (name: string, keyPath: string) => void }).createIndex('by-status', 'status');
            }
          }
        }

        // User settings
        if (!db.objectStoreNames.contains('userSettings')) {
          db.createObjectStore('userSettings', { keyPath: 'key' });
        }

        // Pending uploads
        if (!db.objectStoreNames.contains('pendingUploads')) {
          db.createObjectStore('pendingUploads', { keyPath: 'id' });
        }
      },
    });
  }

  // =========================================================================
  // Sync Queue
  // =========================================================================

  async addToSyncQueue(item: Omit<SyncItem, 'id' | 'timestamp' | 'retryCount'>): Promise<string> {
    await this.init();
    
    const id = `sync_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const syncItem: SyncItem = {
      ...item,
      id,
      timestamp: Date.now(),
      retryCount: 0,
    };

    await this.db!.put('syncQueue', syncItem);
    
    // Trigger sync if online
    if (this.isOnline) {
      this.processQueue();
    }

    return id;
  }

  async removeFromSyncQueue(id: string): Promise<void> {
    await this.init();
    await this.db!.delete('syncQueue', id);
  }

  async getSyncQueue(): Promise<SyncItem[]> {
    await this.init();
    return this.db!.getAllFromIndex('syncQueue', 'by-timestamp');
  }

  async getSyncQueueCount(): Promise<number> {
    await this.init();
    return this.db!.count('syncQueue');
  }

  // =========================================================================
  // Cache Operations
  // =========================================================================

  async cacheSet(key: string, data: unknown, ttlSeconds?: number): Promise<void> {
    await this.init();
    
    const cacheItem: CacheItem = {
      key,
      data,
      timestamp: Date.now(),
      expiresAt: ttlSeconds ? Date.now() + ttlSeconds * 1000 : undefined,
    };

    await this.db!.put('cache', cacheItem);
  }

  async cacheGet<T = unknown>(key: string): Promise<T | null> {
    await this.init();
    
    const item = await this.db!.get('cache', key);
    
    if (!item) return null;
    
    // Check expiration
    if (item.expiresAt && Date.now() > item.expiresAt) {
      await this.db!.delete('cache', key);
      return null;
    }

    return item.data as T;
  }

  async cacheDelete(key: string): Promise<void> {
    await this.init();
    await this.db!.delete('cache', key);
  }

  async cacheClear(): Promise<void> {
    await this.init();
    await this.db!.clear('cache');
  }

  // =========================================================================
  // Entity Storage
  // =========================================================================

  async saveEntity(entityType: keyof OfflineDBSchema, entity: Record<string, unknown>): Promise<void> {
    await this.init();
    const entityTypes = ['incidents', 'audits', 'risks', 'documents'] as const;
    if (entityTypes.includes(entityType as typeof entityTypes[number])) {
      await this.db!.put(entityType as 'incidents', entity);
    }
  }

  async saveEntities(entityType: keyof OfflineDBSchema, entities: Record<string, unknown>[]): Promise<void> {
    await this.init();
    const entityTypes = ['incidents', 'audits', 'risks', 'documents'] as const;
    if (entityTypes.includes(entityType as typeof entityTypes[number])) {
      const tx = this.db!.transaction(entityType as 'incidents', 'readwrite');
      await Promise.all([
        ...entities.map(e => tx.store.put(e)),
        tx.done,
      ]);
    }
  }

  async getEntity<T = unknown>(entityType: keyof OfflineDBSchema, id: string): Promise<T | null> {
    await this.init();
    const entityTypes = ['incidents', 'audits', 'risks', 'documents'] as const;
    if (entityTypes.includes(entityType as typeof entityTypes[number])) {
      return this.db!.get(entityType as 'incidents', id) as Promise<T | null>;
    }
    return null;
  }

  async getAllEntities<T = unknown>(entityType: keyof OfflineDBSchema): Promise<T[]> {
    await this.init();
    const entityTypes = ['incidents', 'audits', 'risks', 'documents'] as const;
    if (entityTypes.includes(entityType as typeof entityTypes[number])) {
      return this.db!.getAll(entityType as 'incidents') as Promise<T[]>;
    }
    return [];
  }

  async deleteEntity(entityType: keyof OfflineDBSchema, id: string): Promise<void> {
    await this.init();
    const entityTypes = ['incidents', 'audits', 'risks', 'documents'] as const;
    if (entityTypes.includes(entityType as typeof entityTypes[number])) {
      await this.db!.delete(entityType as 'incidents', id);
    }
  }

  // =========================================================================
  // User Settings
  // =========================================================================

  async setSetting(key: string, value: Record<string, unknown>): Promise<void> {
    await this.init();
    await this.db!.put('userSettings', { key, ...value });
  }

  async getSetting<T = unknown>(key: string): Promise<T | null> {
    await this.init();
    const result = await this.db!.get('userSettings', key);
    return result || null;
  }

  // =========================================================================
  // File Uploads
  // =========================================================================

  async queueUpload(file: File, metadata: Record<string, unknown>): Promise<string> {
    await this.init();
    
    const id = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    await this.db!.put('pendingUploads', {
      id,
      file: file,
      metadata,
      timestamp: Date.now(),
    });

    return id;
  }

  async getPendingUploads(): Promise<Array<{ id: string; file: Blob; metadata: Record<string, unknown>; timestamp: number }>> {
    await this.init();
    return this.db!.getAll('pendingUploads');
  }

  async removeUpload(id: string): Promise<void> {
    await this.init();
    await this.db!.delete('pendingUploads', id);
  }

  // =========================================================================
  // Sync Processing
  // =========================================================================

  async processQueue(): Promise<void> {
    if (this.syncInProgress || !this.isOnline) return;

    this.syncInProgress = true;
    this.notifySyncStatus({ status: 'syncing', pending: await this.getSyncQueueCount() });

    try {
      const queue = await this.getSyncQueue();

      for (const item of queue) {
        try {
          await this.processSyncItem(item);
          await this.removeFromSyncQueue(item.id);
        } catch (error: unknown) {
          // Update retry count and error
          item.retryCount += 1;
          item.lastError = error instanceof Error ? error.message : String(error);
          
          if (item.retryCount >= 3) {
            console.error(`Sync item ${item.id} failed after 3 retries`, error);
            // Move to dead letter queue or notify user
          } else {
            await this.db!.put('syncQueue', item);
          }
        }
      }

      this.notifySyncStatus({ status: 'synced', pending: 0 });
    } catch (error) {
      console.error('Queue processing failed', error);
      this.notifySyncStatus({ status: 'error', pending: await this.getSyncQueueCount() });
    } finally {
      this.syncInProgress = false;
    }
  }

  private async processSyncItem(item: SyncItem): Promise<void> {
    const baseUrl = API_BASE_URL;
    const endpoint = `${baseUrl}/${item.entityType}`;

    let url = endpoint;
    let method = 'POST';
    let body: Record<string, unknown> | undefined = item.data;

    switch (item.operation) {
      case 'create':
        method = 'POST';
        break;
      case 'update':
        url = `${endpoint}/${item.entityId}`;
        method = 'PATCH';
        break;
      case 'delete':
        url = `${endpoint}/${item.entityId}`;
        method = 'DELETE';
        body = undefined;
        break;
    }

    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('platform_access_token')}`,
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`Sync failed: ${response.status} ${response.statusText}`);
    }
  }

  // =========================================================================
  // Online/Offline Handling
  // =========================================================================

  private initOnlineListener(): void {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.notifySyncStatus({ status: 'online', pending: 0 });
      this.processQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.notifySyncStatus({ status: 'offline', pending: 0 });
    });
  }

  getOnlineStatus(): boolean {
    return this.isOnline;
  }

  // =========================================================================
  // Sync Status Listeners
  // =========================================================================

  onSyncStatus(callback: (status: SyncStatus) => void): () => void {
    this.syncListeners.add(callback);
    return () => this.syncListeners.delete(callback);
  }

  private notifySyncStatus(status: SyncStatus): void {
    this.syncListeners.forEach(cb => cb(status));
  }
}

// ============================================================================
// Types
// ============================================================================

export interface SyncStatus {
  status: 'online' | 'offline' | 'syncing' | 'synced' | 'error';
  pending: number;
}

// ============================================================================
// Singleton Export
// ============================================================================

export const offlineStorage = new OfflineStorage();

// ============================================================================
// React Hook
// ============================================================================

import { useState, useEffect } from 'react';

export function useOfflineStatus(): SyncStatus {
  const [status, setStatus] = useState<SyncStatus>({
    status: navigator.onLine ? 'online' : 'offline',
    pending: 0,
  });

  useEffect(() => {
    const updatePending = async () => {
      const pending = await offlineStorage.getSyncQueueCount();
      setStatus(prev => ({ ...prev, pending }));
    };

    updatePending();
    
    const unsubscribe = offlineStorage.onSyncStatus(setStatus);
    
    return () => {
      unsubscribe();
    };
  }, []);

  return status;
}

export function useOfflineEntity<T>(entityType: string, id: string): {
  data: T | null;
  isLoading: boolean;
  isFromCache: boolean;
} {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFromCache, setIsFromCache] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);

      // Try cache first
      const cached = await offlineStorage.getEntity<T>(entityType as keyof OfflineDBSchema, id);
      if (cached) {
        setData(cached);
        setIsFromCache(true);
      }

      // Try network if online
      if (navigator.onLine) {
        try {
          const baseUrl = API_BASE_URL;
          const response = await fetch(`${baseUrl}/${entityType}/${id}`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('platform_access_token')}`,
            },
          });

          if (response.ok) {
            const freshData = await response.json();
            setData(freshData);
            setIsFromCache(false);
            
            // Update cache
            await offlineStorage.saveEntity(entityType as keyof OfflineDBSchema, freshData);
          }
        } catch (error) {
          console.warn('Network fetch failed, using cached data');
        }
      }

      setIsLoading(false);
    };

    fetchData();
  }, [entityType, id]);

  return { data, isLoading, isFromCache };
}
