/**
 * Sistema de verificación OTP
 * Responsabilidad única: Gestionar envío y verificación de códigos OTP
 */
export class OTPSystem {
    constructor(modalManager, config = {}) {
        this.modal = modalManager;
        this.config = {
            resendTimeout: 60,
            otpLength: 6,
            ...config
        };

        this.state = {
            isVerified: false,
            verifiedPhoneNumber: null,
            resendTimer: null,
            resendTimeLeft: 0
        };

        this.callbacks = {
            onVerified: () => {},
            onFailed: () => {},
            onPhoneChanged: () => {}
        };

        this._bindElements();
        this._bindEvents();
    }

    _bindElements() {
        this.modalPhone = document.getElementById('modal-phone');
        this.sendButton = document.getElementById('send-otp-btn');
        this.sendText = document.getElementById('send-otp-text');
        this.sendSpinner = document.getElementById('send-otp-spinner');

        this.otpInput = document.getElementById('otp-code');
        this.verifyButton = document.getElementById('verify-otp-btn');
        this.verifyText = document.getElementById('verify-otp-text');
        this.verifySpinner = document.getElementById('verify-otp-spinner');

        this.resendButton = document.getElementById('resend-otp-btn');
        this.resendCountdown = document.getElementById('resend-countdown');
        this.otpError = document.getElementById('otp-error');
    }

    _bindEvents() {
        this.sendButton?.addEventListener('click', () => this.sendOTP());
        this.verifyButton?.addEventListener('click', () => this.verifyOTP());
        this.resendButton?.addEventListener('click', () => this.sendOTP(null, true));

        // Validación del input OTP
        this.otpInput?.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');

            if (e.target.value.length === this.config.otpLength) {
                this.verifyButton.disabled = false;
            } else {
                this.verifyButton.disabled = true;
            }

            if (e.target.value.length > 0) {
                this._hideError();
            }
        });

        // Enter para verificar
        this.otpInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.target.value.length === this.config.otpLength && !this.verifyButton.disabled) {
                this.verifyOTP();
            }
        });
    }

    async sendOTP(phoneNumber = null, isResend = false) {
        const phone = phoneNumber || this.modalPhone?.value || '';
        if (!phone) {
            this._showError('Número de teléfono requerido');
            return;
        }

        // Si es un reenvío, deshabilitar inmediatamente y empezar el contador
        if (isResend) {
            this._startResendTimer();
        }

        this._showSendLoading(true);

        try {
            const response = await this._apiRequest('/api/v1/otp/{orderUUID}/send/', {
                purpose: 'PHONE_VERIFICATION',
                recipient: phone
            });

            if (response.success) {
                this.modal.showStep('verify-otp');
                this.otpInput?.focus();

                // Solo iniciar el timer si no es un reenvío (ya se inició arriba)
                if (!isResend) {
                    this._startResendTimer();
                }

                // Debug en desarrollo
                if (response.debug_otp) {
                    console.log('DEBUG OTP Code:', response.debug_otp);
                }
            } else {
                this._showError(response.message || 'Error al enviar el código');
                // Si falla el reenvío, resetear el timer
                if (isResend) {
                    this._clearResendTimer();
                }
            }
        } catch (error) {
            this._showError('Error de conexión. Intenta de nuevo.');
            // Si falla el reenvío, resetear el timer
            if (isResend) {
                this._clearResendTimer();
            }
        }

        this._showSendLoading(false);
    }

    async verifyOTP() {
        const otpCode = this.otpInput?.value;

        if (!otpCode || otpCode.length !== this.config.otpLength) {
            this._showError(`El código debe tener ${this.config.otpLength} dígitos`);
            return;
        }

        this._showVerifyLoading(true);
        this._hideError();

        try {
            const response = await this._apiRequest('/api/v1/otp/{orderUUID}/verify/', {
                otp_code: otpCode,
                purpose: 'PHONE_VERIFICATION'
            });

            if (response.success) {
                this.state.isVerified = true;
                this.state.verifiedPhoneNumber = this.modalPhone?.value;

                this.callbacks.onVerified(this.state.verifiedPhoneNumber);
                this.modal.hide();
                this._resetModal();
            } else {
                this._showError(response.message || 'Código incorrecto');
                this.otpInput?.select();
            }
        } catch (error) {
            this._showError('Error de conexión. Intenta de nuevo.');
        }

        this._showVerifyLoading(false);
    }

    checkPhoneChange(newPhoneNumber) {
        if (this.state.isVerified &&
            this.state.verifiedPhoneNumber &&
            newPhoneNumber !== this.state.verifiedPhoneNumber) {

            this.resetVerification();
            this.callbacks.onPhoneChanged();
        }
    }

    resetVerification() {
        this.state.isVerified = false;
        this.state.verifiedPhoneNumber = null;
        this._clearResendTimer();
    }

    updateModalPhone(phoneNumber) {
        if (this.modalPhone) {
            this.modalPhone.value = phoneNumber;
        }
    }

    // Getters
    isVerified() {
        return this.state.isVerified;
    }

    getVerifiedPhoneNumber() {
        return this.state.verifiedPhoneNumber;
    }

    // API y utilidades
    async _apiRequest(endpoint, data) {
        const orderUUID = this.config.orderUUID || document.body.dataset.orderUuid;
        const baseUrl = this._getBaseUrl();
        const fullEndpoint = baseUrl + endpoint.replace('{orderUUID}', orderUUID);

        console.log('OTP Request:', fullEndpoint, 'Method: POST', data);

        const response = await fetch(fullEndpoint, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this._getCsrfToken()
            },
            body: JSON.stringify(data)
        });

        return await response.json();
    }

    _getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    }

    _getBaseUrl() {
        const isProduction = document.body.dataset.production === 'true';
        return isProduction ? 'https://crm.conquerx.com' : '';
    }

    // UI helpers
    _showSendLoading(show) {
        if (!this.sendButton) return;

        this.sendButton.disabled = show;
        this.sendText.textContent = show ? 'Enviando...' : 'Enviar código';
        if (show) {
            this.sendSpinner?.classList.remove('hidden');
        } else {
            this.sendSpinner?.classList.add('hidden');
        }
    }

    _showVerifyLoading(show) {
        if (!this.verifyButton) return;

        this.verifyButton.disabled = show;
        this.verifyText.textContent = show ? 'Verificando...' : 'Verificar';
        if (show) {
            this.verifySpinner?.classList.remove('hidden');
        } else {
            this.verifySpinner?.classList.add('hidden');
        }
    }

    _showError(message) {
        if (this.otpError) {
            this.otpError.textContent = message;
            this.otpError.classList.remove('hidden');
        }
    }

    _hideError() {
        this.otpError?.classList.add('hidden');
    }

    _startResendTimer() {
        this.state.resendTimeLeft = this.config.resendTimeout;
        this.resendButton.disabled = true;
        this._updateCountdown();

        this.state.resendTimer = setInterval(() => {
            this.state.resendTimeLeft--;
            if (this.state.resendTimeLeft <= 0) {
                this._clearResendTimer();
            } else {
                this._updateCountdown();
            }
        }, 1000);
    }

    _updateCountdown() {
        if (this.state.resendTimeLeft > 0) {
            this.resendCountdown.textContent = `(${this.state.resendTimeLeft}s)`;
            this.resendCountdown.classList.remove('hidden');
        } else {
            this.resendCountdown.classList.add('hidden');
            this.resendButton.disabled = false;
        }
    }

    _clearResendTimer() {
        if (this.state.resendTimer) {
            clearInterval(this.state.resendTimer);
            this.state.resendTimer = null;
        }
        this.state.resendTimeLeft = 0;
        this.resendCountdown?.classList.add('hidden');
        if (this.resendButton) this.resendButton.disabled = false;
    }

    resetModal() {
        this.modal.showStep('send-otp');
        if (this.otpInput) this.otpInput.value = '';
        this._hideError();
        this._showSendLoading(false);
        this._showVerifyLoading(false);
        this._clearResendTimer();
    }

    _resetModal() {
        this.resetModal();
    }

    // Callbacks
    onVerified(callback) {
        this.callbacks.onVerified = callback;
    }

    onFailed(callback) {
        this.callbacks.onFailed = callback;
    }

    onPhoneChanged(callback) {
        this.callbacks.onPhoneChanged = callback;
    }
}