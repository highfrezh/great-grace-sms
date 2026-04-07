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
        this.timerInterval = null;
        this.autoSaveInterval = null;
        this.statusCheckInterval = null;

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
        this.timerInterval = setInterval(() => {
            this.timeRemaining--;
            this.updateUI();

            // Check warning thresholds
            if (this.timeRemaining === this.thresholds.warning) {
                this.showWarning('5 minutes remaining');
            }

            if (this.timeRemaining === this.thresholds.danger) {
                this.showWarning('1 minute remaining - Better hurry!');
            }

            // Auto-submit on timeout
            if (this.timeRemaining === 0) {
                this.handleAutoSubmit('TIME_UP');
            }

            // Update hidden input
            this.timeRemainingInput.value = Math.max(0, this.timeRemaining);
        }, 1000);
    }

    updateUI() {
        // Format and display timer
        const formatted = this.formatTime(this.timeRemaining);
        this.timerDisplay.textContent = formatted;

        // Update document title with time
        document.title = `[${formatted}] Exam`;

        // Apply styling based on time remaining
        this.timerDisplay.classList.remove('warning', 'danger');
        
        if (this.timeRemaining <= this.thresholds.danger) {
            this.timerDisplay.classList.add('danger');
        } else if (this.timeRemaining <= this.thresholds.warning) {
            this.timerDisplay.classList.add('warning');
        }

        // Update progress bar
        const progressPercent = ((this.duration - this.timeRemaining) / this.duration) * 100;
        this.progressFill.style.width = progressPercent + '%';

        // Update answer count
        const answered = document.querySelectorAll('.question-radio:checked').length;
        const total = document.querySelectorAll('.question-radio').length;
        document.getElementById('answeredCount').textContent = answered;
        document.getElementById('timeRemainingText').textContent = formatted;
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
        
        this.autoSaveInterval = setInterval(() => {
            this.autoSave();
        }, this.autoSaveInterval * 1000);
    }

    autoSave() {
        const formData = this.collectAnswers();
        formData.append('time_remaining', this.timeRemaining);
        formData.append('tab_switches', this.tabSwitches);
        formData.append('fullscreen_exits', this.fullscreenExits);

        // Show saving indicator
        this.showSavingIndicator();

        fetch(`/examinations/${this.examId}/autosave/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'saved') {
                this.showSavedIndicator();
                console.log(`✓ Auto-saved ${data.answers_saved} answers`);
            } else if (data.status === 'already_submitted') {
                this.handleAlreadySubmitted();
            }
        })
        .catch(error => {
            console.error('Auto-save failed:', error);
            this.showSaveError();
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
        this.autosaveIndicator.style.display = 'flex';
        this.autosaveDot.classList.add('saving');
        this.autosaveText.textContent = 'Saving...';
    }

    showSavedIndicator() {
        this.autosaveDot.classList.remove('saving');
        this.autosaveText.textContent = 'Saved';
        
        // Hide after 3 seconds
        setTimeout(() => {
            this.autosaveIndicator.style.display = 'none';
        }, 3000);
    }

    showSaveError() {
        this.autosaveDot.classList.remove('saving');
        this.autosaveText.textContent = '⚠ Save failed';
        
        // Show error longer
        setTimeout(() => {
            this.autosaveIndicator.style.display = 'none';
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

        // Log violation
        this.logViolation('FULLSCREEN_EXIT', this.fullscreenExits);

        if (this.fullscreenExits === 1) {
            // First exit: warning
            this.showViolationModal(
                'Fullscreen Warning',
                '⚠️ You have exited fullscreen mode.\n\nThis has been recorded.',
                `Fullscreen exits: ${this.fullscreenExits}/2 (Auto-submit on 2nd)`
            );
        } else if (this.fullscreenExits >= 2) {
            // Second exit: auto-submit
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

        // Log violation
        this.logViolation('TAB_SWITCH', this.tabSwitches);

        if (this.tabSwitches === 1) {
            // First switch: warning
            this.showViolationModal(
                'Tab Switch Warning',
                '⚠️ You have switched to another tab or window.\n\nThis has been recorded.',
                `Tab switches: ${this.tabSwitches}/2 (Auto-submit on 2nd)`
            );
        } else if (this.tabSwitches >= 2) {
            // Second switch: auto-submit
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
        document.getElementById('violationTitle').textContent = title;
        document.getElementById('violationMessage').textContent = message;
        document.getElementById('violationCount').textContent = countInfo;

        this.violationModal.classList.add('show');

        // Auto-close after 5 seconds or on continue button click
        const continueBtn = document.getElementById('continueBtn');
        const autoClose = setTimeout(() => {
            this.violationModal.classList.remove('show');
        }, 5000);

        continueBtn.onclick = () => {
            clearTimeout(autoClose);
            this.violationModal.classList.remove('show');
        };
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

    handleAutoSubmit(reason) {
        clearInterval(this.timerInterval);
        clearInterval(this.autoSaveInterval);
        clearInterval(this.statusCheckInterval);

        document.getElementById('autoSubmitReason').value = reason;

        // Collect final answers
        const formData = new FormData(this.examForm);
        formData.append('time_remaining', 0);
        formData.append('tab_switches', this.tabSwitches);
        formData.append('fullscreen_exits', this.fullscreenExits);
        formData.append('auto_submit_reason', reason);

        // Show auto-submit message
        const message = reason === 'TIME_UP' 
            ? 'Time is up! Your exam is being auto-submitted...'
            : 'Your exam has been auto-submitted due to malpractice violation.';

        this.showWarning(message);

        // Submit exam
        fetch(`/examinations/${this.examId}/auto-submit/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'auto_submitted') {
                // Redirect to results
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Auto-submit failed:', error);
            // Fallback: try form submission
            this.examForm.submit();
        });
    }

    handleAlreadySubmitted() {
        clearInterval(this.timerInterval);
        clearInterval(this.autoSaveInterval);
        clearInterval(this.statusCheckInterval);

        this.showWarning('Exam already submitted! Redirecting...');
        setTimeout(() => {
            window.location.href = `/examinations/${this.examId}/result/`;
        }, 2000);
    }

    // ────────────────────────────────────────────────────────
    // STATUS CHECK
    // ────────────────────────────────────────────────────────

    setupStatusCheck() {
        // Check server status every 30 seconds for connection recovery
        this.statusCheckInterval = setInterval(() => {
            this.checkExamStatus();
        }, 30000);
    }

    checkExamStatus() {
        fetch(`/examinations/${this.examId}/timer-status/`)
            .then(response => response.json())
            .then(data => {
                if (data.is_complete) {
                    this.handleAlreadySubmitted();
                } else if (data.time_remaining !== undefined) {
                    // Update time from server if it's less (connection recovery)
                    if (data.time_remaining < this.timeRemaining) {
                        this.timeRemaining = data.time_remaining;
                    }
                    console.log(`✓ Server status check: ${this.formatTime(this.timeRemaining)}`);
                }
            })
            .catch(error => console.error('Status check failed:', error));
    }

    // ────────────────────────────────────────────────────────
    // FORM SUBMIT
    // ────────────────────────────────────────────────────────

    setupFormSubmit() {
        this.examForm.addEventListener('submit', (e) => {
            // Don't prevent default - let it submit
            clearInterval(this.timerInterval);
            clearInterval(this.autoSaveInterval);
            clearInterval(this.statusCheckInterval);

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
