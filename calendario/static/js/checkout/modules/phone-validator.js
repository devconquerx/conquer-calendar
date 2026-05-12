/**
 * Validador de teléfono con intl-tel-input
 * Responsabilidad única: Validar y gestionar números telefónicos
 */
export class PhoneValidator {
    constructor(phoneInputId, options = {}) {
        this.phoneInput = document.getElementById(phoneInputId);
        this.phonePrefixInput = document.getElementById('phone_prefix');
        this.phoneNumberFull = document.getElementById('phone_number_full');
        this.validationError = document.getElementById('phone-validation-error');

        this.options = {
            preferredCountries: ["es", "co", "mx", "ar", "pe", "cl"],
            separateDialCode: true,
            autoPlaceholder: "aggressive",
            formatAsYouType: true,
            ...options
        };

        this.instance = null;
        this.callbacks = {
            onValidated: () => {},
            onChanged: () => {}
        };

        this.validationTimeout = null;

        this._initialize();
    }

    _initialize() {
        if (!window.intlTelInput) {
            console.error('intlTelInput library not loaded');
            return;
        }

        this.instance = window.intlTelInput(this.phoneInput, {
            ...this.options,
            utilsScript: "https://cdn.jsdelivr.net/npm/intl-tel-input@23.0.4/build/js/utils.js",
            geoIpLookup: (success, failure) => {
                const preselectedCode = this.phoneInput.dataset.countryCode;
                if (preselectedCode) {
                    success(preselectedCode.toLowerCase());
                } else {
                    fetch('https://ipapi.co/json')
                        .then(res => res.json())
                        .then(data => success(data.country_code))
                        .catch(() => failure());
                }
            }
        });

        this._bindEvents();

        // Preservar valor original y dar tiempo al plugin para estabilizarse
        const originalValue = this.phoneInput.value;

        setTimeout(() => {
            // Si había un valor original y el plugin lo cambió, restaurarlo una vez
            if (originalValue && originalValue !== this.phoneInput.value) {
                this.phoneInput.value = originalValue;
            }

            this._updateHiddenFields();

            // Dar más tiempo para validar números precargados
            if (this.phoneInput.value.trim()) {
                setTimeout(() => this._validateNumber(), 1000);
            }
        }, 500);
    }

    _bindEvents() {
        this.phoneInput.addEventListener('input', () => {
            this._updateHiddenFields();
            this.callbacks.onChanged(this.getNumber());

            // Debounce validation - solo validar después de 500ms sin escribir
            clearTimeout(this.validationTimeout);
            this.validationTimeout = setTimeout(() => {
                this._validateNumber();
            }, 500);
        });

        this.phoneInput.addEventListener('countrychange', () => {
            this._validateNumber();
            this._updateHiddenFields();
            this.callbacks.onChanged(this.getNumber());
        });

        // Validar inmediatamente cuando el usuario sale del campo
        this.phoneInput.addEventListener('blur', () => {
            clearTimeout(this.validationTimeout);
            this._validateNumber();
        });
    }

    _validateNumber() {
        if (!this.instance) {
            return false;
        }

        const phoneNumber = this.phoneInput.value.trim();

        if (phoneNumber === '') {
            this._clearValidation();
            return false;
        }

        // Obtener datos del país seleccionado
        const countryData = this.instance.getSelectedCountryData();

        // Intentar obtener el número completo
        let fullNumber = this.instance.getNumber();

        // Si getNumber() no funciona (utils script no cargado), construir manualmente
        if (!fullNumber || fullNumber === '') {
            if (countryData && countryData.dialCode) {
                // Construir número internacional manualmente
                const cleanNumber = phoneNumber.replace(/^0+/, '').replace(/\D/g, '');
                fullNumber = '+' + countryData.dialCode + cleanNumber;
            }
        }

        // Excepción para Andorra: siempre pasar la validación si hay un número
        if (countryData && (countryData.iso2 === 'ad' || countryData.dialCode === '376')) {
            if (phoneNumber.length > 0) {
                this._showValidation(true, '');
                this.callbacks.onValidated(true, fullNumber);
                return true;
            }
        }

        // Validación básica: debe empezar con + y tener al menos 9 dígitos (para países como Andorra)
        const isValidBasic = fullNumber && fullNumber.startsWith('+') && fullNumber.replace(/\D/g, '').length >= 9;

        if (isValidBasic) {
            this._showValidation(true, '');
            this.callbacks.onValidated(true, fullNumber);
            return true;
        } else {
            this._showValidation(false, 'Número de teléfono inválido');
            this.callbacks.onValidated(false, null);
            return false;
        }
    }

    _getErrorMessage(errorCode) {
        const messages = {
            1: 'Código de país inválido',
            2: 'Número muy corto',
            3: 'Número muy largo',
            4: 'Número inválido'
        };
        return messages[errorCode] || 'Número de teléfono inválido';
    }

    _showValidation(isValid, message) {
        if (isValid) {
            this.phoneInput.classList.remove('iti__error');
            this.phoneInput.classList.add('iti__valid');
            this.validationError?.classList.add('hidden');
        } else {
            this.phoneInput.classList.remove('iti__valid');
            this.phoneInput.classList.add('iti__error');
            if (this.validationError) {
                this.validationError.textContent = message;
                this.validationError.classList.remove('hidden');
            }
        }
    }

    _clearValidation() {
        this.phoneInput.classList.remove('iti__error', 'iti__valid');
        this.validationError?.classList.add('hidden');
    }

    _updateHiddenFields() {
        if (!this.instance) return;

        const fullNumber = this.instance.getNumber();
        const countryData = this.instance.getSelectedCountryData();

        if (this.phoneNumberFull) this.phoneNumberFull.value = fullNumber || '';
        if (this.phonePrefixInput) this.phonePrefixInput.value = countryData.dialCode ? '+' + countryData.dialCode : '';
    }

    // Métodos públicos
    isValid() {
        return this.instance ? this.instance.isValidNumber() : false;
    }

    getNumber() {
        return this.instance ? this.instance.getNumber() : '';
    }

    getCountryData() {
        return this.instance ? this.instance.getSelectedCountryData() : null;
    }

    validate() {
        return this._validateNumber();
    }

    focus() {
        this.phoneInput.focus();
        this.phoneInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    rewriteNumber() {
        // Forzar reescritura del número para corregir problemas de validación
        // Retorna una promesa que se resuelve cuando la validación está completa
        return new Promise((resolve) => {
            if (!this.instance) {
                resolve();
                return;
            }

            const currentValue = this.phoneInput.value.trim();
            if (!currentValue) {
                resolve();
                return;
            }

            // Esperar a que el utilsScript esté cargado
            const checkUtilsLoaded = () => {
                return window.intlTelInputUtils !== undefined;
            };

            const waitForUtils = (callback, maxAttempts = 20, attempt = 0) => {
                if (checkUtilsLoaded()) {
                    callback();
                } else if (attempt < maxAttempts) {
                    setTimeout(() => waitForUtils(callback, maxAttempts, attempt + 1), 200);
                } else {
                    callback(); // Continuar de todos modos
                }
            };

            waitForUtils(() => {
                // Obtener datos del país seleccionado
                const countryData = this.instance.getSelectedCountryData();

                // Obtener el número completo internacional (con código de país)
                let fullNumber = this.instance.getNumber();

                // Si el número completo está vacío pero hay un valor, intentar construirlo
                if (!fullNumber && currentValue && countryData && countryData.dialCode) {
                    // Construir el número completo con el código de país
                    fullNumber = '+' + countryData.dialCode + currentValue.replace(/^0+/, '');
                }

                // Limpiar completamente el campo
                this.phoneInput.value = '';
                this.instance.setNumber('');

                // Esperar y reescribir el número completo en formato internacional
                setTimeout(() => {
                    if (fullNumber) {
                        // Usar setNumber en lugar de asignar directamente el value
                        this.instance.setNumber(fullNumber);
                    } else {
                        // Si no hay número completo, usar el valor original
                        this.phoneInput.value = currentValue;
                    }
                    this._updateHiddenFields();

                    // Validar después de un tiempo prudente
                    setTimeout(() => {
                        this._validateNumber();
                        resolve();
                    }, 500);
                }, 200);
            });
        });
    }

    // Callbacks
    onValidated(callback) {
        this.callbacks.onValidated = callback;
    }

    onChanged(callback) {
        this.callbacks.onChanged = callback;
    }
}