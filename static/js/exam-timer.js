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
        this.callbacks = {
            onTick: null,
            onWarning: null,
            onExpiry: null
        };
    }

    /**
     * Start the countdown timer
     */
    start() {
        if (this.isRunning) return;
        
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
        if (!timerWidget) return;
        
        // Warning at 1 minute (60 seconds)
        if (this.remaining === 60) {
            timerWidget.classList.add('warning');
            timerWidget.classList.remove('danger');
            if (this.callbacks.onWarning) {
                this.callbacks.onWarning('1 minute remaining');
            }
        }
        
        // Danger at 30 seconds
        if (this.remaining === 30) {
            timerWidget.classList.remove('warning');
            timerWidget.classList.add('danger');
            if (this.callbacks.onWarning) {
                this.callbacks.onWarning('30 seconds remaining');
            }
        }
        
        // Time expired
        if (this.remaining === 0) {
            timerWidget.classList.remove('warning');
            timerWidget.classList.add('danger');
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
