/**
 * Exam Timer Component
 * Countdown timer for OSCE station evaluation
 */

class ExamTimer {
    constructor(durationMinutes, elementId = 'timer') {
        this.duration = durationMinutes * 60; // Convert to seconds
        this.remaining = this.duration;
        this.elementId = elementId;
        this.interval = null;
        this.isRunning = false;
        this.soundPlayed = {
            oneMinute: false,
            thirtySeconds: false,
            expiry: false
        };
        this.callbacks = {
            onTick: null,
            onWarning: null,
            onExpiry: null
        };
        this.audioContext = null; // Lazy-initialized on first start() to satisfy browser autoplay policy
    }

    /**
     * Initialize Web Audio API context for sound generation.
     * Must be called from within a user-gesture handler (e.g. start()).
     */
    initAudioContext() {
        if (this.audioContext) return;
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
        } catch(e) {
            console.warn('Web Audio API not supported:', e);
        }
    }

    /**
     * Play a beep sound using Web Audio API.
     * Resumes the AudioContext first in case the browser suspended it.
     */
    playBeep(frequency = 1000, duration = 500) {
        if (!this.audioContext) return;
        
        const doPlay = () => {
            try {
                const ctx = this.audioContext;
                const oscillator = ctx.createOscillator();
                const gainNode = ctx.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(ctx.destination);
                
                oscillator.frequency.value = frequency;
                oscillator.type = 'sine';
                
                gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration / 1000);
                
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + duration / 1000);
            } catch(e) {
                console.warn('Error playing beep:', e);
            }
        };

        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(doPlay).catch(e => console.warn('AudioContext resume failed:', e));
        } else {
            doPlay();
        }
    }

    /**
     * Start the countdown timer
     */
    start() {
        if (this.isRunning) return;

        // Initialize (or resume) AudioContext inside a user-gesture handler
        this.initAudioContext();
        if (this.audioContext && this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        this.isRunning = true;
        this.render();
        
        this.interval = setInterval(() => {
            this.remaining--;
            this.render();
            this.checkWarnings();
            
            if (this.callbacks.onTick) {
                this.callbacks.onTick(this.remaining);
            }
            
            if (this.remaining <= 0) {
                this.stop();
                if (this.callbacks.onExpiry) {
                    this.callbacks.onExpiry();
                }
            }
        }, 1000);
    }

    /**
     * Stop/pause the timer
     */
    stop() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
            this.isRunning = false;
        }
    }

    /**
     * Reset timer to initial duration
     */
    reset() {
        this.stop();
        this.remaining = this.duration;
        this.soundPlayed = {
            oneMinute: false,
            thirtySeconds: false,
            expiry: false
        };
        this.render();
        this.removeWarningClass();
    }

    /**
     * Render timer display (MM:SS format)
     */
    render() {
        const element = document.getElementById(this.elementId);
        if (!element) {
            console.error(`Timer element #${this.elementId} not found`);
            return;
        }
        
        const minutes = Math.floor(Math.abs(this.remaining) / 60);
        const seconds = Math.abs(this.remaining) % 60;
        
        const sign = this.remaining < 0 ? '-' : '';
        const timeString = `${sign}${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        element.textContent = timeString;
    }

    /**
     * Check and apply warning states
     */
    checkWarnings() {
        const timerWidget = document.querySelector('.timer-widget');
        const timerInline = document.getElementById('timer-inline');
        if (!timerWidget) return;
        
        // Warning at 1 minute (60 seconds)
        if (this.remaining === 60) {
            timerWidget.classList.add('warning');
            timerWidget.classList.remove('danger');
            if (timerInline) { timerInline.classList.add('warning'); timerInline.classList.remove('danger'); }
            
            // Play beep sound on first occurrence
            if (!this.soundPlayed.oneMinute) {
                this.playBeep(800, 400); // 800Hz, 400ms
                this.soundPlayed.oneMinute = true;
            }
            
            if (this.callbacks.onWarning) {
                this.callbacks.onWarning('1 minute remaining');
            }
        }
        
        // Danger at 30 seconds
        if (this.remaining === 30) {
            timerWidget.classList.remove('warning');
            timerWidget.classList.add('danger');
            if (timerInline) { timerInline.classList.remove('warning'); timerInline.classList.add('danger'); }
            if (this.callbacks.onWarning) {
                this.callbacks.onWarning('30 seconds remaining');
            }
        }
        
        // Time expired
        if (this.remaining === 0) {
            timerWidget.classList.remove('warning');
            timerWidget.classList.add('danger');
            if (timerInline) { timerInline.classList.remove('warning'); timerInline.classList.add('danger'); }
            if (this.callbacks.onWarning) {
                this.callbacks.onWarning('Time is up!');
            }
        }
    }

    /**
     * Remove warning classes
     */
    removeWarningClass() {
        const timerWidget = document.querySelector('.timer-widget');
        if (timerWidget) {
            timerWidget.classList.remove('warning', 'danger');
        }
        const timerInline = document.getElementById('timer-inline');
        if (timerInline) {
            timerInline.classList.remove('warning', 'danger');
        }
    }

    /**
     * Register callback functions
     */
    on(event, callback) {
        if (this.callbacks.hasOwnProperty('on' + event.charAt(0).toUpperCase() + event.slice(1))) {
            this.callbacks['on' + event.charAt(0).toUpperCase() + event.slice(1)] = callback;
        }
    }

    /**
     * Get remaining time in seconds
     */
    getRemainingSeconds() {
        return this.remaining;
    }

    /**
     * Get remaining time formatted as MM:SS
     */
    getRemainingFormatted() {
        const minutes = Math.floor(Math.abs(this.remaining) / 60);
        const seconds = Math.abs(this.remaining) % 60;
        const sign = this.remaining < 0 ? '-' : '';
        return `${sign}${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    /**
     * Get percentage of time remaining
     */
    getPercentageRemaining() {
        return (this.remaining / this.duration) * 100;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExamTimer;
}
