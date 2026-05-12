/**
 * Gestor de estado centralizado para el checkout
 * Responsabilidad única: Coordinar el estado entre todos los módulos
 */
export class CheckoutState {
    constructor() {
        this.state = {
            phone: {
                valid: false,
                number: null,
                changed: false
            },
            otp: {
                verified: false,
                verifiedPhone: null,
                required: false
            },
            terms: {
                accepted: false
            },
            form: {
                valid: false,
                canSubmit: false
            },
            gateway: {
                selected: null,
                isStripe: false
            },
            order: {
                uuid: null,
                exists: false
            },
            config: {
                otpVerificationEnabled: true,
                otpExceptionNumbers: []
            }
        };

        this.callbacks = {
            onStateChanged: () => {},
            onSubmitStateChanged: () => {}
        };

        this.submitButton = document.getElementById('submit-button');
        this.termsCheckbox = document.getElementById('terms-checkbox');

        this._loadInitialState();
    }

    _loadInitialState() {
        // Cargar configuración desde el DOM
        const body = document.body;
        this.state.config.otpVerificationEnabled = body.dataset.checkoutOtpVerificationEnabled === 'true';
        this.state.order.uuid = body.dataset.orderUuid || null;
        this.state.order.exists = !!this.state.order.uuid;

        // Cargar números de excepción OTP
        const numbersString = body.dataset.otpExceptionNumbers || '';
        this.state.config.otpExceptionNumbers = numbersString ? numbersString.split(',').map(num => num.trim()) : [];

        // Estado inicial de términos
        if (this.termsCheckbox) {
            this.state.terms.accepted = this.termsCheckbox.checked;
        }

        // OTP siempre es requerido
        this.state.otp.required = true;

        this._updateSubmitButton();
    }

    // Método auxiliar para verificar números de excepción OTP
    _isPhoneExceptionNumber(phoneNumber) {
        return this.state.config.otpExceptionNumbers.includes(phoneNumber);
    }

    // Métodos de actualización de estado
    updatePhoneState(isValid, phoneNumber = null) {
        const wasValid = this.state.phone.valid;
        const oldNumber = this.state.phone.number;

        this.state.phone.valid = isValid;
        this.state.phone.number = phoneNumber;
        this.state.phone.changed = oldNumber && oldNumber !== phoneNumber;

        // Si el teléfono cambió, resetear verificación OTP
        if (this.state.phone.changed && this.state.otp.verified) {
            this.resetOTPVerification();
        }

        if (wasValid !== isValid) {
            this._notifyStateChange();
        }

        this._updateSubmitButton();
    }

    updateOTPVerification(isVerified, verifiedPhone = null) {
        this.state.otp.verified = isVerified;
        this.state.otp.verifiedPhone = verifiedPhone;

        // Si se verificó, aceptar términos automáticamente
        if (isVerified && this.termsCheckbox) {
            this.state.terms.accepted = true;
            this.termsCheckbox.checked = true;
            this.termsCheckbox.disabled = true;
        }

        this._notifyStateChange();
        this._updateSubmitButton();
    }

    resetOTPVerification() {
        this.state.otp.verified = false;
        this.state.otp.verifiedPhone = null;

        // Rehabilitar términos
        if (this.termsCheckbox) {
            this.termsCheckbox.checked = false;
            this.termsCheckbox.disabled = false;
        }
        this.state.terms.accepted = false;

        this._notifyStateChange();
        this._updateSubmitButton();
    }

    updateTermsAcceptance(accepted) {
        this.state.terms.accepted = accepted;
        this._notifyStateChange();
        this._updateSubmitButton();
    }

    updateGatewaySelection(gatewayId, isStripe = false) {
        this.state.gateway.selected = gatewayId;
        this.state.gateway.isStripe = isStripe;

        this._notifyStateChange();
        this._updateSubmitButton();
    }

    updateOrderState(uuid, exists) {
        this.state.order.uuid = uuid;
        this.state.order.exists = exists;

        this._notifyStateChange();
    }

    // Validaciones de estado
    isPhoneValid() {
        return this.state.phone.valid;
    }

    isOTPRequired() {
        return this.state.otp.required;
    }

    isOTPVerified() {
        return this.state.otp.verified;
    }

    areTermsAccepted() {
        return this.state.terms.accepted;
    }

    canSubmitForm() {
        // Validaciones básicas
        if (!this.areTermsAccepted()) {
            return { canSubmit: false, reason: 'terms_required' };
        }

        // Validación de teléfono siempre requerida
        if (!this.isPhoneValid()) {
            return { canSubmit: false, reason: 'phone_invalid' };
        }

        // Validación OTP solo requerida si está habilitada (excepto para números de excepción)
        if (this.state.config.otpVerificationEnabled) {
            if (!this.isOTPVerified() && !this._isPhoneExceptionNumber(this.state.phone.number)) {
                return { canSubmit: false, reason: 'otp_required' };
            }
        }

        return { canSubmit: true, reason: null };
    }

    needsOTPVerification() {
        // Omitir verificación OTP si está deshabilitada
        if (!this.state.config.otpVerificationEnabled) {
            return false;
        }

        // Omitir verificación OTP para números de excepción
        if (this._isPhoneExceptionNumber(this.state.phone.number)) {
            return false;
        }

        return this.isPhoneValid() &&
               !this.isOTPVerified();
    }

    // Gestión del botón de envío
    _updateSubmitButton() {
        if (!this.submitButton) return;

        const submitState = this.canSubmitForm();
        this.state.form.canSubmit = submitState.canSubmit;

        if (submitState.canSubmit) {
            this._enableSubmitButton();
        } else {
            this._disableSubmitButton();
        }

        this.callbacks.onSubmitStateChanged(submitState);
    }

    _enableSubmitButton() {
        if (!this.submitButton) return;

        this.submitButton.disabled = false;
        this.submitButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
        this.submitButton.classList.add('bg-green-600', 'hover:bg-green-700', 'cursor-pointer');
    }

    _disableSubmitButton() {
        if (!this.submitButton) return;

        this.submitButton.disabled = true;
        this.submitButton.classList.add('bg-gray-400', 'cursor-not-allowed');
        this.submitButton.classList.remove('bg-green-600', 'hover:bg-green-700', 'cursor-pointer');
    }

    // Utilidades de acceso
    getState() {
        return { ...this.state };
    }

    getPhoneNumber() {
        return this.state.phone.number;
    }

    getVerifiedPhoneNumber() {
        return this.state.otp.verifiedPhone;
    }

    isStripeSelected() {
        return this.state.gateway.isStripe;
    }

    getOrderUUID() {
        return this.state.order.uuid;
    }

    orderExists() {
        return this.state.order.exists;
    }

    isOTPVerificationEnabled() {
        return this.state.config.otpVerificationEnabled;
    }

    // Notificaciones
    _notifyStateChange() {
        this.callbacks.onStateChanged(this.getState());
    }

    // Callbacks
    onStateChanged(callback) {
        this.callbacks.onStateChanged = callback;
    }

    onSubmitStateChanged(callback) {
        this.callbacks.onSubmitStateChanged = callback;
    }

    // Debug
    logState() {
        console.log('Current checkout state:', this.getState());
    }
}