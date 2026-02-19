/**
 * OSCE Examiner - Core JavaScript Module
 * 
 * Handles:
 * - Offline data storage with IndexedDB
 * - Sync queue management
 * - Touch interactions
 * - Timer functionality
 */

// ==========================================================================
// IndexedDB Storage
// ==========================================================================

class ExaminerDB {
    constructor() {
        this.dbName = 'OSCEExaminerDB';
        this.dbVersion = 1;
        this.db = null;
    }
    
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Scores store - keyed by station_id + student_id
                if (!db.objectStoreNames.contains('scores')) {
                    const scoresStore = db.createObjectStore('scores', { 
                        keyPath: ['stationId', 'studentId'] 
                    });
                    scoresStore.createIndex('synced', 'synced', { unique: false });
                    scoresStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
                
                // Sync queue for pending uploads
                if (!db.objectStoreNames.contains('syncQueue')) {
                    const queueStore = db.createObjectStore('syncQueue', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    queueStore.createIndex('type', 'type', { unique: false });
                    queueStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
                
                // Cache for session data
                if (!db.objectStoreNames.contains('cache')) {
                    db.createObjectStore('cache', { keyPath: 'key' });
                }
            };
        });
    }
    
    async saveScore(stationId, studentId, itemId, score, isCritical = false) {
        const tx = this.db.transaction('scores', 'readwrite');
        const store = tx.objectStore('scores');
        
        // Get existing record or create new
        const key = [stationId, studentId];
        let record = await this._getFromStore(store, key);
        
        if (!record) {
            record = {
                stationId,
                studentId,
                items: {},
                globalRating: null,
                comments: '',
                synced: false,
                timestamp: Date.now()
            };
        }
        
        // Update item score
        record.items[itemId] = {
            score,
            isCritical,
            timestamp: Date.now()
        };
        record.synced = false;
        record.timestamp = Date.now();
        
        await this._putInStore(store, record);
        
        // Add to sync queue
        await this.addToSyncQueue('itemScore', {
            stationId,
            studentId,
            itemId,
            score,
            isCritical,
            timestamp: Date.now()
        });
        
        return record;
    }
    
    async saveGlobalRating(stationId, studentId, rating) {
        const tx = this.db.transaction('scores', 'readwrite');
        const store = tx.objectStore('scores');
        
        const key = [stationId, studentId];
        let record = await this._getFromStore(store, key);
        
        if (!record) {
            record = {
                stationId,
                studentId,
                items: {},
                globalRating: null,
                comments: '',
                synced: false,
                timestamp: Date.now()
            };
        }
        
        record.globalRating = rating;
        record.synced = false;
        record.timestamp = Date.now();
        
        await this._putInStore(store, record);
        
        // Add to sync queue
        await this.addToSyncQueue('globalRating', {
            stationId,
            studentId,
            rating,
            timestamp: Date.now()
        });
        
        return record;
    }
    
    async getScores(stationId, studentId) {
        const tx = this.db.transaction('scores', 'readonly');
        const store = tx.objectStore('scores');
        return await this._getFromStore(store, [stationId, studentId]);
    }
    
    async addToSyncQueue(type, data) {
        const tx = this.db.transaction('syncQueue', 'readwrite');
        const store = tx.objectStore('syncQueue');
        
        await this._addToStore(store, {
            type,
            data,
            timestamp: Date.now(),
            attempts: 0
        });
    }
    
    async getSyncQueue() {
        const tx = this.db.transaction('syncQueue', 'readonly');
        const store = tx.objectStore('syncQueue');
        return await this._getAllFromStore(store);
    }
    
    async clearSyncedItems(ids) {
        const tx = this.db.transaction('syncQueue', 'readwrite');
        const store = tx.objectStore('syncQueue');
        
        for (const id of ids) {
            await this._deleteFromStore(store, id);
        }
    }
    
    async markScoresAsSynced(stationId, studentId) {
        const tx = this.db.transaction('scores', 'readwrite');
        const store = tx.objectStore('scores');
        
        const record = await this._getFromStore(store, [stationId, studentId]);
        if (record) {
            record.synced = true;
            await this._putInStore(store, record);
        }
    }
    
    // Cache methods for session data
    async setCache(key, data, expiresIn = 3600000) {
        const tx = this.db.transaction('cache', 'readwrite');
        const store = tx.objectStore('cache');
        
        await this._putInStore(store, {
            key,
            data,
            expires: Date.now() + expiresIn
        });
    }
    
    async getCache(key) {
        const tx = this.db.transaction('cache', 'readonly');
        const store = tx.objectStore('cache');
        
        const record = await this._getFromStore(store, key);
        if (record && record.expires > Date.now()) {
            return record.data;
        }
        return null;
    }
    
    // Helper methods
    _getFromStore(store, key) {
        return new Promise((resolve, reject) => {
            const request = store.get(key);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    _getAllFromStore(store) {
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    _putInStore(store, data) {
        return new Promise((resolve, reject) => {
            const request = store.put(data);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    _addToStore(store, data) {
        return new Promise((resolve, reject) => {
            const request = store.add(data);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    _deleteFromStore(store, key) {
        return new Promise((resolve, reject) => {
            const request = store.delete(key);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
}

// ==========================================================================
// Sync Manager
// ==========================================================================

class SyncManager {
    constructor(db) {
        this.db = db;
        this.isSyncing = false;
        this.apiBase = '/examiner/api';
    }
    
    async sync() {
        if (this.isSyncing || !navigator.onLine) {
            return { success: false, reason: this.isSyncing ? 'already syncing' : 'offline' };
        }
        
        this.isSyncing = true;
        const results = { synced: 0, failed: 0, errors: [] };
        
        try {
            const queue = await this.db.getSyncQueue();
            const syncedIds = [];
            
            for (const item of queue) {
                try {
                    await this.syncItem(item);
                    syncedIds.push(item.id);
                    results.synced++;
                } catch (error) {
                    results.failed++;
                    results.errors.push({
                        id: item.id,
                        error: error.message
                    });
                    
                    // Retry logic - give up after 5 attempts
                    if (item.attempts >= 5) {
                        syncedIds.push(item.id); // Remove from queue
                        console.error('Giving up on sync item after 5 attempts:', item);
                    }
                }
            }
            
            if (syncedIds.length > 0) {
                await this.db.clearSyncedItems(syncedIds);
            }
            
            // Update UI
            this.updateSyncStatus(results);
            
            return { success: true, results };
            
        } catch (error) {
            console.error('Sync failed:', error);
            return { success: false, error: error.message };
        } finally {
            this.isSyncing = false;
        }
    }
    
    async syncItem(item) {
        const response = await fetch(`${this.apiBase}/sync`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(item)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    updateSyncStatus(results) {
        const badge = document.getElementById('pending-count');
        if (badge) {
            const queue = this.db.getSyncQueue().then(q => {
                badge.textContent = q.length;
                badge.style.display = q.length > 0 ? 'inline' : 'none';
            });
        }
    }
    
    startAutoSync(intervalMs = 30000) {
        setInterval(() => {
            if (navigator.onLine) {
                this.sync();
            }
        }, intervalMs);
        
        // Sync when coming back online
        window.addEventListener('online', () => {
            console.log('Back online, syncing...');
            this.sync();
        });
    }
}

// ==========================================================================
// Timer
// ==========================================================================

class StationTimer {
    constructor(displayElement, durationMinutes = 5, onComplete = null) {
        this.display = displayElement;
        this.duration = durationMinutes * 60;
        this.remaining = this.duration;
        this.intervalId = null;
        this.isRunning = false;
        this.onComplete = onComplete;
        this.warnings = [60, 30]; // Warning thresholds in seconds
    }
    
    start() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.intervalId = setInterval(() => this.tick(), 1000);
        this.updateDisplay();
    }
    
    pause() {
        if (!this.isRunning) return;
        
        this.isRunning = false;
        clearInterval(this.intervalId);
    }
    
    reset() {
        this.pause();
        this.remaining = this.duration;
        this.updateDisplay();
        this.display.classList.remove('text-warning', 'text-danger');
    }
    
    tick() {
        this.remaining--;
        
        if (this.remaining <= 0) {
            this.pause();
            this.remaining = 0;
            if (this.onComplete) {
                this.onComplete();
            }
            // Play sound or vibrate
            this.notifyComplete();
        } else if (this.warnings.includes(this.remaining)) {
            this.notifyWarning();
        }
        
        this.updateDisplay();
    }
    
    updateDisplay() {
        const minutes = Math.floor(this.remaining / 60);
        const seconds = this.remaining % 60;
        const formatted = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (this.display) {
            this.display.textContent = formatted;
            
            // Color coding
            if (this.remaining <= 30) {
                this.display.classList.remove('text-warning');
                this.display.classList.add('text-danger');
            } else if (this.remaining <= 60) {
                this.display.classList.add('text-warning');
            }
        }
    }
    
    notifyWarning() {
        if ('vibrate' in navigator) {
            navigator.vibrate(200);
        }
    }
    
    notifyComplete() {
        if ('vibrate' in navigator) {
            navigator.vibrate([200, 100, 200, 100, 200]);
        }
        
        // Play audio if available
        const audio = document.getElementById('timer-audio');
        if (audio) {
            audio.play().catch(() => {});
        }
    }
}

// ==========================================================================
// Touch Interactions
// ==========================================================================

class SwipeHandler {
    constructor(element, onSwipeLeft, onSwipeRight, threshold = 100) {
        this.element = element;
        this.onSwipeLeft = onSwipeLeft;
        this.onSwipeRight = onSwipeRight;
        this.threshold = threshold;
        this.startX = 0;
        this.startY = 0;
        
        this.init();
    }
    
    init() {
        this.element.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: true });
        this.element.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
        this.element.addEventListener('touchend', (e) => this.handleTouchEnd(e), { passive: true });
    }
    
    handleTouchStart(e) {
        this.startX = e.touches[0].clientX;
        this.startY = e.touches[0].clientY;
    }
    
    handleTouchMove(e) {
        if (!this.startX || !this.startY) return;
        
        const diffX = e.touches[0].clientX - this.startX;
        const diffY = e.touches[0].clientY - this.startY;
        
        // Only handle horizontal swipes
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 20) {
            e.preventDefault();
        }
    }
    
    handleTouchEnd(e) {
        const diffX = e.changedTouches[0].clientX - this.startX;
        const diffY = e.changedTouches[0].clientY - this.startY;
        
        if (Math.abs(diffX) > this.threshold && Math.abs(diffX) > Math.abs(diffY)) {
            if (diffX > 0 && this.onSwipeRight) {
                this.onSwipeRight();
            } else if (diffX < 0 && this.onSwipeLeft) {
                this.onSwipeLeft();
            }
        }
        
        this.startX = 0;
        this.startY = 0;
    }
}

// ==========================================================================
// Marking Interface
// ==========================================================================

class MarkingInterface {
    constructor(options = {}) {
        this.stationId = options.stationId;
        this.studentId = options.studentId;
        this.db = options.db;
        this.syncManager = options.syncManager;
        this.totalMarks = 0;
        this.earnedMarks = 0;
        this.criticalFailed = false;
    }
    
    async init() {
        // Load any existing scores from IndexedDB
        const existing = await this.db.getScores(this.stationId, this.studentId);
        if (existing) {
            this.restoreScores(existing);
        }
        
        // Bind event handlers
        this.bindEvents();
        
        // Calculate initial totals
        this.calculateTotals();
    }
    
    bindEvents() {
        // Score buttons
        document.querySelectorAll('.score-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleScoreClick(e));
        });
        
        // Global rating
        document.querySelectorAll('.rating-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleRatingClick(e));
        });
        
        // Next student
        const nextBtn = document.getElementById('next-student');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextStudent());
        }
    }
    
    async handleScoreClick(e) {
        const btn = e.currentTarget;
        const item = btn.closest('.checklist-item');
        const itemId = item.dataset.itemId;
        const score = btn.dataset.score === '1' ? 1 : 0;
        const isCritical = item.classList.contains('critical-item');
        
        // Visual feedback
        item.querySelectorAll('.score-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update item styling
        item.classList.remove('marked-done', 'marked-not-done');
        item.classList.add(score === 1 ? 'marked-done' : 'marked-not-done');
        
        // Save to IndexedDB
        await this.db.saveScore(this.stationId, this.studentId, itemId, score, isCritical);
        
        // Check critical failure
        if (isCritical && score === 0) {
            this.criticalFailed = true;
            this.showCriticalWarning();
        }
        
        // Update totals
        this.calculateTotals();
        
        // Update pending count
        this.updatePendingCount();
    }
    
    async handleRatingClick(e) {
        const btn = e.currentTarget;
        const rating = parseInt(btn.dataset.rating);
        
        // Visual feedback
        document.querySelectorAll('.rating-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Save to IndexedDB
        await this.db.saveGlobalRating(this.stationId, this.studentId, rating);
        
        // Update pending count
        this.updatePendingCount();
    }
    
    calculateTotals() {
        let total = 0;
        let earned = 0;
        
        document.querySelectorAll('.checklist-item').forEach(item => {
            const marks = parseFloat(item.dataset.marks) || 1;
            total += marks;
            
            const doneBtn = item.querySelector('.score-btn.done.active');
            if (doneBtn) {
                earned += marks;
            }
        });
        
        this.totalMarks = total;
        this.earnedMarks = earned;
        
        // Update display
        const display = document.getElementById('running-total');
        if (display) {
            display.textContent = `${earned}/${total}`;
            
            // Percentage coloring
            const pct = total > 0 ? (earned / total) * 100 : 0;
            display.classList.remove('text-danger', 'text-warning', 'text-success');
            if (pct < 50) {
                display.classList.add('text-danger');
            } else if (pct < 70) {
                display.classList.add('text-warning');
            } else {
                display.classList.add('text-success');
            }
        }
    }
    
    restoreScores(record) {
        // Restore item scores
        for (const [itemId, data] of Object.entries(record.items)) {
            const item = document.querySelector(`.checklist-item[data-item-id="${itemId}"]`);
            if (item) {
                const btn = item.querySelector(`.score-btn[data-score="${data.score}"]`);
                if (btn) {
                    btn.classList.add('active');
                    item.classList.add(data.score === 1 ? 'marked-done' : 'marked-not-done');
                }
            }
        }
        
        // Restore global rating
        if (record.globalRating !== null) {
            const ratingBtn = document.querySelector(`.rating-btn[data-rating="${record.globalRating}"]`);
            if (ratingBtn) {
                ratingBtn.classList.add('active');
            }
        }
    }
    
    showCriticalWarning() {
        const toast = document.createElement('div');
        toast.className = 'alert alert-danger position-fixed bottom-0 start-50 translate-middle-x mb-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <strong>⚠️ Critical Item Failed!</strong><br>
            This may affect the overall station pass/fail status.
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }
    
    async updatePendingCount() {
        const queue = await this.db.getSyncQueue();
        const badge = document.getElementById('pending-count');
        if (badge) {
            badge.textContent = queue.length;
            badge.style.display = queue.length > 0 ? 'inline-block' : 'none';
        }
    }
    
    nextStudent() {
        // Navigate to next student in sequence
        const currentIndex = parseInt(document.body.dataset.studentIndex) || 0;
        const nextIndex = currentIndex + 1;
        
        // This would be populated from the session data
        const studentList = JSON.parse(document.body.dataset.studentList || '[]');
        
        if (nextIndex < studentList.length) {
            window.location.href = `/examiner/station/${this.stationId}/student/${studentList[nextIndex].id}`;
        } else {
            // All students done
            alert('All students have been marked for this station!');
        }
    }
}

// ==========================================================================
// Global Initialization
// ==========================================================================

let examinerDB = null;
let syncManager = null;

async function initExaminer() {
    // Initialize IndexedDB
    examinerDB = new ExaminerDB();
    await examinerDB.init();
    
    // Initialize sync manager
    syncManager = new SyncManager(examinerDB);
    syncManager.startAutoSync();
    
    // Update offline status
    updateOnlineStatus();
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    
    console.log('Examiner module initialized');
    return { db: examinerDB, sync: syncManager };
}

function updateOnlineStatus() {
    const banner = document.getElementById('offline-banner');
    if (banner) {
        banner.style.display = navigator.onLine ? 'none' : 'block';
    }
    
    // Update sync button if exists
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.disabled = !navigator.onLine;
    }
}

// Export for use in templates
window.ExaminerDB = ExaminerDB;
window.SyncManager = SyncManager;
window.StationTimer = StationTimer;
window.SwipeHandler = SwipeHandler;
window.MarkingInterface = MarkingInterface;
window.initExaminer = initExaminer;
