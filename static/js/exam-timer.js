/**
 * ExamTimer - Comprehensive exam control system
 * Handles: Server-side timer, auto-save, fullscreen, tab detection, malpractice logging
 */

class ExamTimer {
    constructor(config) {
        this.examId = config.examId;
        this.duration = config.duration * 60; // Convert minutes to seconds
        this.timeRemaining = config.initialTime;
        this.autoSaveInterval = config.autoSaveInterval || 30;
        this.thresholds = config.timerThresholds || { warning: 300, danger: 60 };

        // Malpractice counters
        this.tabSwitches = 0;
        this.fullscreenExits = 0;
        this.isFullscreen = false;
        this.lastWindowFocus = true;

        // Timers
        this.timerIntervalId = null;
        this.autoSaveIntervalId = null;
        this.statusCheckIntervalId = null;

        // DOM elements
        this.timerDisplay = document.getElementById('timerDisplay');
        this.autosaveIndicator = document.getElementById('autosaveIndicator');
        this.autosaveDot = document.getElementById('autosaveDot');
        this.autosaveText = document.getElementById('autosaveText');
        this.progressFill = document.getElementById('progressFill');
        this.timeRemainingInput = document.getElementById('timeRemaining');
        this.tabSwitchesInput = document.getElementById('tabSwitches');
        this.fullscreenExitsInput = document.getElementById('fullscreenExits');
        this.violationModal = document.getElementById('violationModal');
        this.examForm = document.getElementById('examForm');
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        this.init();
    }

    init() {
        this.startTimer();
        this.setupAutoSave();
        this.setupFullscreenEnforcement();
        this.setupTabDetection();
        this.setupStatusCheck();
        this.setupFormSubmit();
        this.requestFullscreen();
        this.updateUI();

        console.log('✓ ExamTimer initialized');
        console.log(`✓ Time remaining: ${this.formatTime(this.timeRemaining)}`);
        console.log(`✓ Auto-save interval: ${this.autoSaveInterval}s`);
    }

    // ────────────────────────────────────────────────────────
    // TIMER MANAGEMENT
    // ────────────────────────────────────────────────────────

    startTimer() {
        const tick = () => {
            if (this._isSubmitting) return;

            this.timeRemaining--;
            
            // Auto-submit on timeout
            if (this.timeRemaining <= 0) {
                this.timeRemaining = 0;
                this.updateUI();
                this.handleAutoSubmit('TIME_UP');
                return; // Stop the loop
            }
            
            this.updateUI();

            // Check warning thresholds
            if (this.timeRemaining === this.thresholds.warning) {
                this.showWarning('5 minutes remaining');
            }

            if (this.timeRemaining === this.thresholds.danger) {
                this.showWarning('1 minute remaining - Better hurry!');
            }

            // Update hidden input
            if (this.timeRemainingInput) {
                this.timeRemainingInput.value = Math.max(0, this.timeRemaining);
            }

            // Recursive call for more reliability than setInterval
            this.timerIntervalId = setTimeout(tick, 1000);
        };
        
        tick(); // Start immediately
    }

    syncWithServer() {
        if (this._isSubmitting) return;

        fetch(`/examinations/${this.examId}/timer-status/`)
            .then(r => r.json())
            .then(data => {
                if (data.is_complete) {
                    this.handleAlreadySubmitted();
                    return;
                }
                
                // Sync if server time is less (connection recovery or drift)
                if (data.time_remaining !== undefined && data.time_remaining < this.timeRemaining) {
                    console.log('⟳ Syncing timer with server:', this.formatTime(data.time_remaining));
                    this.timeRemaining = data.time_remaining;
                    this.updateUI();
                }

                if (this.timeRemaining <= 0) {
                    this.handleAutoSubmit('TIME_UP');
                }
            })
            .catch(error => console.error('Sync failed:', error));
    }

    updateUI() {
        // Format and display timer
        const formatted = this.formatTime(this.timeRemaining);
        
        if (this.timerDisplay) {
            this.timerDisplay.textContent = formatted;
        }

        // Update document title with time
        document.title = `[${formatted}] Exam`;

        // Apply styling based on time remaining
        if (this.timerDisplay) {
            this.timerDisplay.classList.remove('warning', 'danger');
            
            if (this.timeRemaining <= this.thresholds.danger) {
                this.timerDisplay.classList.add('danger');
            } else if (this.timeRemaining <= this.thresholds.warning) {
                this.timerDisplay.classList.add('warning');
            }
        }

        // Update progress bar
        if (this.progressFill) {
            const progressPercent = ((this.duration - this.timeRemaining) / this.duration) * 100;
            this.progressFill.style.width = progressPercent + '%';
        }

        // Update answer count
        const answeredCountEl = document.getElementById('answeredCount');
        if (answeredCountEl) {
            const answered = document.querySelectorAll('.question-radio:checked').length;
            answeredCountEl.textContent = answered;
        }

        const timeRemainingTextEl = document.getElementById('timeRemainingText');
        if (timeRemainingTextEl) {
            timeRemainingTextEl.textContent = formatted;
        }
    }

    checkExamStatus() {
        // Alias for compatibility if needed elsewhere, but redirects to syncWithServer
        this.syncWithServer();
    }

    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) {
            return `${hours}h ${String(mins).padStart(2, '0')}m`;
        } else {
            return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }
    }

    // ────────────────────────────────────────────────────────
    // AUTO-SAVE
    // ────────────────────────────────────────────────────────

    setupAutoSave() {
        this.autoSave();  // Save immediately
        
        const duration = this.autoSaveInterval * 1000;
        this.autoSaveIntervalId = setInterval(() => {
            this.autoSave();
        }, duration);
    }

    autoSave() {
        if (this._isSubmitting) return;

        // Add timeout to prevent blocking auto-submit
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            console.warn('⚠ Auto-save request timed out and was aborted.');
            controller.abort();
        }, 5000);

        const formData = this.collectAnswers();
        formData.append('time_remaining', this.timeRemaining);
        formData.append('tab_switches', this.tabSwitches);
        formData.append('fullscreen_exits', this.fullscreenExits);
        formData.append('csrfmiddlewaretoken', this.csrfToken);

        // Show saving indicator
        this.showSavingIndicator();

        fetch(`/examinations/${this.examId}/autosave/`, {
            method: 'POST',
            body: formData,
            signal: controller.signal,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.csrfToken
            }
        })
        .then(async response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.status === 'saved') {
                this.showSavedIndicator();
                console.log(`✓ Auto-saved ${data.answers_saved} answers`);
            } else if (data.status === 'already_submitted') {
                this.handleAlreadySubmitted();
            }
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                console.error('Auto-save aborted due to timeout');
            } else {
                console.error('Auto-save failed:', error);
            }
            this.showSaveError();
        })
        .finally(() => {
            clearTimeout(timeoutId);
        });
    }

    collectAnswers() {
        const formData = new FormData();
        
        document.querySelectorAll('.question-radio:checked').forEach(radio => {
            formData.append(radio.name, radio.value);
        });

        return formData;
    }

    showSavingIndicator() {
        if (this.autosaveIndicator) this.autosaveIndicator.style.display = 'flex';
        if (this.autosaveDot) this.autosaveDot.classList.add('saving');
        if (this.autosaveText) this.autosaveText.textContent = 'Saving...';
    }

    showSavedIndicator() {
        if (this.autosaveDot) this.autosaveDot.classList.remove('saving');
        if (this.autosaveText) this.autosaveText.textContent = 'Saved';
        
        // Hide after 3 seconds
        setTimeout(() => {
            if (this.autosaveIndicator) this.autosaveIndicator.style.display = 'none';
        }, 3000);
    }

    showSaveError() {
        if (this.autosaveDot) this.autosaveDot.classList.remove('saving');
        if (this.autosaveText) this.autosaveText.textContent = '⚠ Save failed';
        
        // Show error longer
        setTimeout(() => {
            if (this.autosaveIndicator) this.autosaveIndicator.style.display = 'none';
        }, 5000);
    }

    // ────────────────────────────────────────────────────────
    // FULLSCREEN ENFORCEMENT
    // ────────────────────────────────────────────────────────

    requestFullscreen() {
        const elem = document.documentElement;
        
        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch(() => {
                console.log('Fullscreen request denied');
            });
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.mozRequestFullScreen) {
            elem.mozRequestFullScreen();
        }
    }

    setupFullscreenEnforcement() {
        // Monitor fullscreen state
        document.addEventListener('fullscreenchange', () => {
            this.isFullscreen = !!document.fullscreenElement;
            if (!this.isFullscreen) {
                this.handleFullscreenExit();
            }
        });

        document.addEventListener('webkitfullscreenchange', () => {
            this.isFullscreen = !!document.webkitFullscreenElement;
            if (!this.isFullscreen) {
                this.handleFullscreenExit();
            }
        });

        // Prevent ESC key (may not work in all browsers)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                this.handleFullscreenExit();
            }
        });
    }

    handleFullscreenExit() {
        this.fullscreenExits++;
        this.fullscreenExitsInput.value = this.fullscreenExits;

        // Log violation removed

        if (this.fullscreenExits <= 2) {
            // First and second exits: warnings
            const warningTitle = this.fullscreenExits === 2 ? 'FINAL WARNING - Fullscreen Violation' : 'Warning - Fullscreen Violation';
            this.showViolationModal(
                warningTitle,
                '⚠️ You have exited fullscreen mode. This is strictly prohibited during the examination.',
                `Violation Count: ${this.fullscreenExits}/3 (Exam will be submitted on Attempt #3)`
            );
        } else if (this.fullscreenExits >= 3) {
            // Third exit: auto-submit
            this.handleAutoSubmit('FULLSCREEN_VIOLATION');
        }

        // Re-request fullscreen
        setTimeout(() => {
            this.requestFullscreen();
        }, 1000);
    }

    // ────────────────────────────────────────────────────────
    // TAB SWITCH DETECTION
    // ────────────────────────────────────────────────────────

    setupTabDetection() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.handleTabHidden();
            } else {
                this.handleTabVisible();
            }
        });

        window.addEventListener('blur', () => {
            this.lastWindowFocus = false;
        });

        window.addEventListener('focus', () => {
            this.lastWindowFocus = true;
        });
    }

    handleTabHidden() {
        console.log('⚠ Student switched tabs/windows');
        this.tabSwitches++;
        this.tabSwitchesInput.value = this.tabSwitches;

        // Log violation removed

        if (this.tabSwitches <= 2) {
            // First and second switches: warnings
            const warningTitle = this.tabSwitches === 2 ? 'FINAL WARNING - Tab Switch' : 'Warning - Tab Switch';
            this.showViolationModal(
                warningTitle,
                '⚠️ You have switched to another tab or window. This is prohibited during the examination.',
                `Violation Count: ${this.tabSwitches}/3 (Exam will be submitted on Attempt #3)`
            );
        } else if (this.tabSwitches >= 3) {
            // Third switch: auto-submit
            this.handleAutoSubmit('TAB_SWITCH_VIOLATION');
        }
    }

    handleTabVisible() {
        // Optional: bring exam back to focus
        window.focus();
    }

    // ────────────────────────────────────────────────────────
    // VIOLATIONS & MODALS
    // ────────────────────────────────────────────────────────

    logViolation(type, count) {
        const formData = new FormData();
        formData.append('violation_type', type);
        formData.append('violation_count', count);
        formData.append('violation_details', `Violation #${count}`);

        fetch(`/examinations/${this.examId}/autosave/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).catch(error => console.error('Violation logging failed:', error));
    }

    showViolationModal(title, message, countInfo) {
        const titleEl = document.getElementById('violationTitle');
        const messageEl = document.getElementById('violationMessage');
        const countEl = document.getElementById('violationCount');

        if (titleEl) titleEl.textContent = title;
        if (messageEl) messageEl.textContent = message;
        if (countEl) countEl.textContent = countInfo;

        if (this.violationModal) {
            this.violationModal.classList.add('show');

            // Auto-close after 5 seconds or on continue button click
            const continueBtn = document.getElementById('continueBtn');
            const autoClose = setTimeout(() => {
                this.violationModal.classList.remove('show');
            }, 5000);

            if (continueBtn) {
                continueBtn.onclick = () => {
                    clearTimeout(autoClose);
                    this.violationModal.classList.remove('show');
                };
            }
        }
    }

    showWarning(message) {
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 999;
            font-weight: 600;
            animation: slideUp 0.3s ease-out;
        `;
        toast.textContent = '⏱ ' + message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideDown 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ────────────────────────────────────────────────────────
    // AUTO-SUBMIT
    // ────────────────────────────────────────────────────────

    async handleAutoSubmit(reason) {
        if (this._isSubmitting) return;
        this._isSubmitting = true;

        console.log(`⚠ Initiating auto-submit. Reason: ${reason}`);

        // 1. Immediate Cleanup
        clearTimeout(this.timerIntervalId);
        clearInterval(this.autoSaveIntervalId);
        clearInterval(this.statusCheckIntervalId);

        // 2. Visual Feedback
        const message = reason === 'TIME_UP' 
            ? 'Time is up! Submitting your exam...'
            : 'Auto-submitting due to violation...';
        
        if (typeof this.showWarning === 'function') {
            this.showWarning(message);
        }

        // 3. Robust AJAX Auto-Submit (Primary Method)
        try {
            const formData = this.collectAnswers();
            formData.append('tab_switches', this.tabSwitches);
            formData.append('fullscreen_exits', this.fullscreenExits);
            formData.append('auto_submit_reason', reason);
            formData.append('time_remaining', 0);
            formData.append('csrfmiddlewaretoken', this.csrfToken);

            const response = await fetch(`/examinations/${this.examId}/auto-submit/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.redirect_url) {
                    console.log('🚀 AJAX auto-submit successful. Redirecting...');
                    window.location.href = data.redirect_url;
                    return;
                }
            }
        } catch (error) {
            console.error('AJAX auto-submit failed, falling back to form:', error);
        }

        // 4. Fallback: Native Form Submission
        // Populate hidden fields just in case
        const reasonInput = document.getElementById('autoSubmitReason');
        if (reasonInput) reasonInput.value = reason;
        const timeRemainingInput = document.getElementById('timeRemaining');
        if (timeRemainingInput) timeRemainingInput.value = 0;

        console.log('🚀 Executing fallback native form submission');
        const submitBtn = document.getElementById('hiddenSubmitBtn');
        if (submitBtn) {
            submitBtn.click();
        } else {
            this.examForm.submit();
        }

        // 5. Final Fallback: Force Navigation
        setTimeout(() => {
            const fallbackUrl = `/examinations/${this.examId}/result/`;
            console.log(`Final Fallback: Redirection to ${fallbackUrl}`);
            window.location.href = fallbackUrl;
        }, 3000);
    }

    handleAlreadySubmitted() {
        clearTimeout(this.timerIntervalId);
        clearInterval(this.autoSaveIntervalId);
        clearInterval(this.statusCheckIntervalId);

        this.showWarning('Exam already submitted! Redirecting...');
        setTimeout(() => {
            window.location.href = `/examinations/${this.examId}/result/`;
        }, 2000);
    }

    // ────────────────────────────────────────────────────────
    // STATUS CHECK
    // ────────────────────────────────────────────────────────

    setupStatusCheck() {
        // Check server status every 60 seconds for synchronization
        this.statusCheckIntervalId = setInterval(() => {
            this.syncWithServer();
        }, 60000);
    }

    // syncWithServer is now implemented above near startTimer

    // ────────────────────────────────────────────────────────
    // FORM SUBMIT
    // ────────────────────────────────────────────────────────

    setupFormSubmit() {
        this.examForm.addEventListener('submit', (e) => {
            // Don't prevent default - let it submit
            clearTimeout(this.timerIntervalId);
            clearInterval(this.autoSaveIntervalId);
            clearInterval(this.statusCheckIntervalId);

            // Update state before submit
            this.tabSwitchesInput.value = this.tabSwitches;
            this.fullscreenExitsInput.value = this.fullscreenExits;
            this.timeRemainingInput.value = this.timeRemaining;
        });

        // Handle review button
        const reviewBtn = document.getElementById('reviewBtn');
        if (reviewBtn) {
            reviewBtn.addEventListener('click', (e) => {
                e.preventDefault();
                // Scroll to show answered/unanswered questions
                const unanswered = document.querySelector('.question-radio:not(:checked)');
                if (unanswered) {
                    unanswered.closest('.question-item').scrollIntoView({ behavior: 'smooth' });
                }
            });
        }
    }
}

// Add CSS animations to head
const style = document.createElement('style');
style.textContent = `
    @keyframes slideUp {
        from { transform: translateY(100px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    @keyframes slideDown {
        from { transform: translateY(0); opacity: 1; }
        to { transform: translateY(100px); opacity: 0; }
    }
`;
document.head.appendChild(style);

console.log('✓ ExamTimer library loaded');
