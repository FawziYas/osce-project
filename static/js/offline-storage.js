/**
 * OSCE Examiner - Offline Storage Module
 * 
 * Provides IndexedDB-based offline storage for:
 * - Caching checklist data
 * - Storing scores locally when offline
 * - Queue management for syncing
 * 
 * This module wraps the core ExaminerDB functionality
 * and provides a simple API for other modules.
 */

// ==========================================================================
// Offline Storage Manager
// ==========================================================================

class OfflineStorage {
    constructor() {
        this.dbName = 'OSCEOfflineStorage';
        this.dbVersion = 1;
        this.db = null;
        this.isReady = false;
    }

    /**
     * Initialize the offline storage database
     */
    async init() {
        if (this.isReady) return this.db;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('OfflineStorage: Failed to open database', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.isReady = true;
                console.log('OfflineStorage: Database ready');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Store for cached API responses
                if (!db.objectStoreNames.contains('apiCache')) {
                    const cacheStore = db.createObjectStore('apiCache', { keyPath: 'url' });
                    cacheStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                // Store for offline scores
                if (!db.objectStoreNames.contains('offlineScores')) {
                    const scoresStore = db.createObjectStore('offlineScores', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    scoresStore.createIndex('stationScoreId', 'stationScoreId', { unique: false });
                    scoresStore.createIndex('synced', 'synced', { unique: false });
                }

                // Store for pending form submissions
                if (!db.objectStoreNames.contains('pendingSubmissions')) {
                    const submissionsStore = db.createObjectStore('pendingSubmissions', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    submissionsStore.createIndex('type', 'type', { unique: false });
                    submissionsStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                console.log('OfflineStorage: Database schema created/upgraded');
            };
        });
    }

    /**
     * Cache an API response for offline use
     */
    async cacheApiResponse(url, data, ttlMs = 3600000) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('apiCache', 'readwrite');
        const store = tx.objectStore('apiCache');

        const record = {
            url,
            data,
            timestamp: Date.now(),
            expires: Date.now() + ttlMs
        };

        return new Promise((resolve, reject) => {
            const request = store.put(record);
            request.onsuccess = () => resolve(true);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get cached API response
     */
    async getCachedResponse(url) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('apiCache', 'readonly');
        const store = tx.objectStore('apiCache');

        return new Promise((resolve, reject) => {
            const request = store.get(url);
            request.onsuccess = () => {
                const record = request.result;
                if (record && record.expires > Date.now()) {
                    resolve(record.data);
                } else {
                    resolve(null);
                }
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Save a score locally for offline sync
     */
    async saveOfflineScore(stationScoreId, itemId, score, maxPoints) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('offlineScores', 'readwrite');
        const store = tx.objectStore('offlineScores');

        const record = {
            stationScoreId,
            itemId,
            score,
            maxPoints,
            timestamp: Date.now(),
            synced: false
        };

        return new Promise((resolve, reject) => {
            const request = store.add(record);
            request.onsuccess = () => {
                console.log('OfflineStorage: Score saved offline', record);
                resolve(request.result);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get all unsynced scores
     */
    async getUnsyncedScores() {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('offlineScores', 'readonly');
        const store = tx.objectStore('offlineScores');
        const index = store.index('synced');

        return new Promise((resolve, reject) => {
            // Use 0 instead of false for IndexedDB key (boolean not valid as key)
            const request = index.getAll(IDBKeyRange.only(0));
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Mark scores as synced
     */
    async markScoresAsSynced(ids) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('offlineScores', 'readwrite');
        const store = tx.objectStore('offlineScores');

        const promises = ids.map(id => {
            return new Promise((resolve, reject) => {
                const getRequest = store.get(id);
                getRequest.onsuccess = () => {
                    const record = getRequest.result;
                    if (record) {
                        record.synced = true;
                        const putRequest = store.put(record);
                        putRequest.onsuccess = () => resolve();
                        putRequest.onerror = () => reject(putRequest.error);
                    } else {
                        resolve();
                    }
                };
                getRequest.onerror = () => reject(getRequest.error);
            });
        });

        return Promise.all(promises);
    }

    /**
     * Add a pending submission to the queue
     */
    async addPendingSubmission(type, data) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('pendingSubmissions', 'readwrite');
        const store = tx.objectStore('pendingSubmissions');

        const record = {
            type,
            data,
            timestamp: Date.now(),
            attempts: 0
        };

        return new Promise((resolve, reject) => {
            const request = store.add(record);
            request.onsuccess = () => {
                console.log('OfflineStorage: Pending submission added', record);
                resolve(request.result);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get all pending submissions
     */
    async getPendingSubmissions() {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('pendingSubmissions', 'readonly');
        const store = tx.objectStore('pendingSubmissions');

        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Remove a pending submission after successful sync
     */
    async removePendingSubmission(id) {
        if (!this.isReady) await this.init();

        const tx = this.db.transaction('pendingSubmissions', 'readwrite');
        const store = tx.objectStore('pendingSubmissions');

        return new Promise((resolve, reject) => {
            const request = store.delete(id);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Clear all cached data (useful for logout)
     */
    async clearAll() {
        if (!this.isReady) await this.init();

        const stores = ['apiCache', 'offlineScores', 'pendingSubmissions'];
        
        for (const storeName of stores) {
            const tx = this.db.transaction(storeName, 'readwrite');
            const store = tx.objectStore(storeName);
            await new Promise((resolve, reject) => {
                const request = store.clear();
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            });
        }

        console.log('OfflineStorage: All data cleared');
    }

    /**
     * Get storage statistics
     */
    async getStats() {
        if (!this.isReady) await this.init();

        const stats = {
            cachedResponses: 0,
            offlineScores: 0,
            pendingSubmissions: 0
        };

        const stores = ['apiCache', 'offlineScores', 'pendingSubmissions'];
        const keys = ['cachedResponses', 'offlineScores', 'pendingSubmissions'];

        for (let i = 0; i < stores.length; i++) {
            const tx = this.db.transaction(stores[i], 'readonly');
            const store = tx.objectStore(stores[i]);
            stats[keys[i]] = await new Promise((resolve) => {
                const request = store.count();
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => resolve(0);
            });
        }

        return stats;
    }
}

// ==========================================================================
// Global Instance
// ==========================================================================

// Create and export a global instance
window.offlineStorage = new OfflineStorage();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.offlineStorage.init().catch(err => {
        console.warn('OfflineStorage: Initialization failed', err);
    });
});

// Helper function for templates
window.saveOfflineScore = async function(itemId, score, maxPoints) {
    if (typeof MARKING_DATA !== 'undefined' && MARKING_DATA.stationScoreId) {
        try {
            await window.offlineStorage.saveOfflineScore(
                MARKING_DATA.stationScoreId,
                itemId,
                score,
                maxPoints
            );
            return true;
        } catch (error) {
            console.error('Failed to save offline score:', error);
            return false;
        }
    }
    return false;
};
