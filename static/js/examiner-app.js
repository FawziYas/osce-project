/**
 * OSCE Examiner - Main Application Module
 * 
 * Handles:
 * - Application initialization
 * - Online/offline sync coordination
 * - UI state management
 * - Global event handlers
 */

// ==========================================================================
// Application State
// ==========================================================================

const ExaminerApp = {
    isOnline: navigator.onLine,
    syncInProgress: false,
    lastSyncTime: null,
    syncInterval: null,

    /**
     * Initialize the application
     */
    async init() {
        console.log('ExaminerApp: Initializing...');

        // Setup online/offline listeners
        this.setupNetworkListeners();

        // Setup sync interval
        this.setupSyncInterval();

        // Initialize UI
        this.updateOnlineUI();

        // Try initial sync if online
        if (this.isOnline) {
            this.syncPendingData();
        }

        console.log('ExaminerApp: Initialized');
    },

    /**
     * Setup network status listeners
     */
    setupNetworkListeners() {
        window.addEventListener('online', () => {
            console.log('ExaminerApp: Back online');
            this.isOnline = true;
            this.updateOnlineUI();
            this.showToast('Back online! Syncing data...', 'success');
            this.syncPendingData();
        });

        window.addEventListener('offline', () => {
            console.log('ExaminerApp: Gone offline');
            this.isOnline = false;
            this.updateOnlineUI();
            this.showToast('You are offline. Changes will be saved locally.', 'warning');
        });
    },

    /**
     * Setup periodic sync interval
     */
    setupSyncInterval() {
        // Sync every 30 seconds when online
        this.syncInterval = setInterval(() => {
            if (this.isOnline && !this.syncInProgress) {
                this.syncPendingData();
            }
        }, 30000);
    },

    /**
     * Update UI based on online/offline status
     */
    updateOnlineUI() {
        const indicator = document.getElementById('offline-indicator');
        if (indicator) {
            if (this.isOnline) {
                indicator.classList.add('d-none');
            } else {
                indicator.classList.remove('d-none');
            }
        }

        // Update sync status indicators
        const syncStatus = document.getElementById('sync-status');
        if (syncStatus) {
            if (this.isOnline) {
                syncStatus.innerHTML = '<i class="bi bi-cloud-check text-success"></i>';
                syncStatus.title = 'Connected';
            } else {
                syncStatus.innerHTML = '<i class="bi bi-cloud-slash text-warning"></i>';
                syncStatus.title = 'Offline - changes saved locally';
            }
        }
    },

    /**
     * Sync all pending offline data
     */
    async syncPendingData() {
        if (this.syncInProgress || !this.isOnline) return;

        this.syncInProgress = true;
        console.log('ExaminerApp: Starting sync...');

        try {
            // Get pending scores from offline storage
            if (window.offlineStorage) {
                const unsyncedScores = await window.offlineStorage.getUnsyncedScores();
                
                if (unsyncedScores.length > 0) {
                    console.log(`ExaminerApp: Syncing ${unsyncedScores.length} offline scores`);
                    
                    const syncedIds = [];
                    
                    for (const score of unsyncedScores) {
                        try {
                            const response = await fetch(`/api/score/${score.stationScoreId}/item`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    checklist_item_id: score.itemId,
                                    score: score.score,
                                    max_points: score.maxPoints
                                })
                            });

                            if (response.ok) {
                                syncedIds.push(score.id);
                            }
                        } catch (err) {
                            console.warn('ExaminerApp: Failed to sync score', score, err);
                        }
                    }

                    if (syncedIds.length > 0) {
                        await window.offlineStorage.markScoresAsSynced(syncedIds);
                        console.log(`ExaminerApp: Synced ${syncedIds.length} scores`);
                    }
                }

                // Sync pending submissions
                const pendingSubmissions = await window.offlineStorage.getPendingSubmissions();
                
                for (const submission of pendingSubmissions) {
                    try {
                        const response = await this.replaySubmission(submission);
                        if (response.ok) {
                            await window.offlineStorage.removePendingSubmission(submission.id);
                        }
                    } catch (err) {
                        console.warn('ExaminerApp: Failed to sync submission', submission, err);
                    }
                }
            }

            this.lastSyncTime = new Date();
            console.log('ExaminerApp: Sync complete');

        } catch (error) {
            console.error('ExaminerApp: Sync failed', error);
        } finally {
            this.syncInProgress = false;
        }
    },

    /**
     * Replay a pending submission
     */
    async replaySubmission(submission) {
        switch (submission.type) {
            case 'scoreSubmit':
                return fetch(`/api/score/${submission.data.stationScoreId}/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(submission.data)
                });
            
            default:
                console.warn('ExaminerApp: Unknown submission type', submission.type);
                return { ok: true }; // Remove unknown submissions
        }
    },

    /**
     * Show a toast notification
     */
    showToast(message, type = 'info') {
        // Check if toast container exists, create if not
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            toastContainer.style.zIndex = '1100';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'toast-' + Date.now();
        const bgClass = {
            'success': 'bg-success',
            'warning': 'bg-warning',
            'error': 'bg-danger',
            'info': 'bg-info'
        }[type] || 'bg-info';

        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 4000 });
        toast.show();

        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    },

    /**
     * Make a fetch request with offline fallback
     */
    async fetchWithOffline(url, options = {}) {
        try {
            if (this.isOnline) {
                const response = await fetch(url, options);
                
                // Cache GET responses
                if (options.method === undefined || options.method === 'GET') {
                    const data = await response.clone().json();
                    if (window.offlineStorage) {
                        await window.offlineStorage.cacheApiResponse(url, data);
                    }
                }
                
                return response;
            } else {
                // Offline - try cache for GET requests
                if (options.method === undefined || options.method === 'GET') {
                    if (window.offlineStorage) {
                        const cached = await window.offlineStorage.getCachedResponse(url);
                        if (cached) {
                            return new Response(JSON.stringify(cached), {
                                status: 200,
                                headers: { 'Content-Type': 'application/json' }
                            });
                        }
                    }
                }
                
                // For POST/PUT requests while offline, queue them
                if (options.method === 'POST' || options.method === 'PUT') {
                    if (window.offlineStorage) {
                        await window.offlineStorage.addPendingSubmission('apiRequest', {
                            url,
                            options
                        });
                    }
                    // Return a fake success response
                    return new Response(JSON.stringify({ success: true, offline: true }), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' }
                    });
                }
                
                throw new Error('Offline and no cached data available');
            }
        } catch (error) {
            console.error('ExaminerApp: Fetch failed', url, error);
            throw error;
        }
    },

    /**
     * Confirm dialog with promise
     */
    confirm(message) {
        return new Promise((resolve) => {
            resolve(window.confirm(message));
        });
    },

    /**
     * Format time for display
     */
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    /**
     * Debounce function for input handlers
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// ==========================================================================
// Timer Functionality
// ==========================================================================

const StationTimer = {
    remainingSeconds: 0,
    intervalId: null,
    isRunning: false,
    onComplete: null,
    warningOneMinutePlayed: false,
    warningThirtySecondsPlayed: false,
    audioContext: null,

    /**
     * Start the station timer
     */
    start(durationMinutes, onComplete = null) {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.remainingSeconds = durationMinutes * 60;
        this.onComplete = onComplete;
        this.isRunning = true;
        this.warningOneMinutePlayed = false;
        this.warningThirtySecondsPlayed = false;
        this.updateDisplay();

        this.intervalId = setInterval(() => {
            if (this.remainingSeconds > 0) {
                this.remainingSeconds--;
                this.updateDisplay();

                // Warning at 1 minute
                if (this.remainingSeconds === 60 && !this.warningOneMinutePlayed) {
                    this.warningOneMinutePlayed = true;
                    ExaminerApp.showToast('1 minute remaining!', 'warning');
                    this.playWarningBell();
                }

                // Warning at 30 seconds
                if (this.remainingSeconds === 30 && !this.warningThirtySecondsPlayed) {
                    this.warningThirtySecondsPlayed = true;
                    ExaminerApp.showToast('30 seconds remaining!', 'warning');
                }
            } else {
                this.stop();
                ExaminerApp.showToast('Time is up!', 'error');
                if (this.onComplete) {
                    this.onComplete();
                }
            }
        }, 1000);
    },

    /**
     * Stop the timer
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.isRunning = false;
    },

    /**
     * Pause the timer
     */
    pause() {
        this.stop();
    },

    /**
     * Resume the timer
     */
    resume() {
        if (!this.isRunning && this.remainingSeconds > 0) {
            this.start(this.remainingSeconds / 60, this.onComplete);
        }
    },

    /**
     * Play a short bell tone for warnings
     */
    playWarningBell() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;

            if (!this.audioContext) {
                this.audioContext = new AudioCtx();
            }

            const ctx = this.audioContext;
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(880, ctx.currentTime);

            gainNode.gain.setValueAtTime(0.0001, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
            gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.8);

            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);

            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + 0.8);
        } catch (err) {
            console.warn('StationTimer: unable to play warning bell', err);
        }
    },

    /**
     * Update the timer display
     */
    updateDisplay() {
        const timerEl = document.getElementById('timer');
        if (timerEl) {
            timerEl.textContent = ExaminerApp.formatTime(this.remainingSeconds);

            // Change color based on remaining time
            if (this.remainingSeconds <= 60) {
                timerEl.classList.add('text-danger');
                timerEl.classList.remove('text-warning');
            } else {
                timerEl.classList.remove('text-danger', 'text-warning');
            }
        }
    },

    /**
     * Get remaining time
     */
    getRemaining() {
        return {
            minutes: Math.floor(this.remainingSeconds / 60),
            seconds: this.remainingSeconds % 60,
            totalSeconds: this.remainingSeconds
        };
    }
};

// ==========================================================================
// Touch Interactions
// ==========================================================================

const TouchHandler = {
    /**
     * Setup touch-friendly interactions
     */
    init() {
        // Prevent double-tap zoom on buttons
        document.querySelectorAll('button, .btn').forEach(btn => {
            btn.addEventListener('touchend', (e) => {
                e.preventDefault();
                btn.click();
            });
        });

        // Add touch feedback
        document.querySelectorAll('.checklist-item, .btn').forEach(el => {
            el.addEventListener('touchstart', () => {
                el.style.transform = 'scale(0.98)';
            });
            el.addEventListener('touchend', () => {
                el.style.transform = '';
            });
        });
    }
};

// ==========================================================================
// Offline Checklist Loader
// ==========================================================================

/**
 * Load checklist from offline storage when API is unavailable
 */
async function loadOfflineChecklist() {
    if (!window.offlineStorage) {
        console.warn('Offline storage not available');
        return null;
    }

    const url = `/api/station/${MARKING_DATA.stationId}/checklist`;
    const cached = await window.offlineStorage.getCachedResponse(url);

    if (cached) {
        console.log('Loading checklist from cache');
        renderChecklist(cached);
        return cached;
    }

    // Show error if no cached data
    const container = document.getElementById('checklist-container');
    if (container) {
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="bi bi-wifi-off me-2"></i>
                <strong>Offline</strong><br>
                Unable to load checklist. Please connect to the internet and try again.
            </div>
        `;
    }

    return null;
}

// ==========================================================================
// Initialization
// ==========================================================================

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ExaminerApp.init();
    TouchHandler.init();

    // Timer will be started from the marking page's DOMContentLoaded handler
    // to ensure MARKING_DATA is available
});

// Export for global use
window.ExaminerApp = ExaminerApp;
window.StationTimer = StationTimer;
window.loadOfflineChecklist = loadOfflineChecklist;
