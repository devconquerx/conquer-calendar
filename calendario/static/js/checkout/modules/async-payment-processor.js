/**
 * Módulo para procesamiento asíncrono de pagos en el checkout.
 * Reemplaza el submit síncrono del formulario por llamadas AJAX.
 */

import { NotificationManager } from '../utils/notifications.js';

export class AsyncPaymentProcessor {
    constructor(checkoutForm, options = {}) {
        this.form = checkoutForm;
        this.shortCode = options.shortCode || document.body.dataset.shortCode;
        this.notifications = new NotificationManager();

        // Estado del procesamiento
        this.isProcessing = false;

        // URLs para las APIs
        this.baseUrl = this._getBaseUrl();
        this.processUrl = `${this.baseUrl}/c/api/${this.shortCode}/process/`;
        this.statusUrl = null; // Se establece después del procesamiento

        // Callbacks
        this.onProcessingStart = options.onProcessingStart || (() => {});
        this.onProcessingEnd = options.onProcessingEnd || (() => {});
        this.onSuccess = options.onSuccess || this._defaultSuccessHandler.bind(this);
        this.onError = options.onError || this._defaultErrorHandler.bind(this);

        this._bindEvents();
    }

    _bindEvents() {
        // El submit del formulario se maneja desde CheckoutApp
        // Este procesador solo se llama directamente mediante processPayment()
    }

    async processPayment() {
        if (this.isProcessing) {
            return;
        }

        this.isProcessing = true;

        // IMPORTANTE: Capturar datos del formulario ANTES de deshabilitar campos
        this.capturedFormData = this._captureFormData();

        this.onProcessingStart();

        try {
            // Verificar si es pago con Stripe o Whop
            const selectedGateway = this.form.querySelector('input[name="gateway_id"]:checked');
            const gatewayId = selectedGateway ? selectedGateway.value : null;

            // Determinar el método de pago por el card visual seleccionado
            const paymentMethodCard = document.querySelector(`[data-gateway="${gatewayId}"]`);
            const isStripe = paymentMethodCard && paymentMethodCard.querySelector('img[alt="Stripe"]') !== null;
            const isWhop = (paymentMethodCard && paymentMethodCard.querySelector('img[alt="Whop"]') !== null)
                || (document.body.dataset.isDualPayment === 'true' && document.body.dataset.dualActiveSegmentOrder === '2');

            if (isStripe) {
                await this._processStripePayment();
            } else if (isWhop) {
                await this._processWhopPayment();
            } else {
                await this._processStandardPayment();
            }

        } catch (error) {
            console.error('[AsyncPaymentProcessor] ❌ Payment processing error:', error);
            this._handleNetworkError(error);
        } finally {
            this.isProcessing = false;
            this.onProcessingEnd();
        }
    }

    async _processStripePayment() {
        // Acceder a Stripe desde la instancia global
        const stripe = window.checkoutApp?.stripe;
        const stripeElements = window.checkoutApp?.stripeElements;

        if (!stripe || !stripeElements) {
            throw new Error('Stripe no está inicializado correctamente');
        }

        // Obtener billing_details del formulario para mejorar tasa de aceptación
        const billingDetails = this._getBillingDetails();

        // Confirmar el pago con Stripe Elements
        const result = await stripe.confirmPayment({
            elements: stripeElements,
            redirect: 'if_required',
            confirmParams: {
                return_url: window.location.origin + '/checkout/success/',
                payment_method_data: {
                    billing_details: billingDetails
                }
            }
        });

        if (result.error) {
            this._handleErrorResponse({
                success: false,
                error: result.error.message,
                error_type: 'stripe_payment_error',
                gateway_code: 'STRIPE'
            });
        } else {
            // Para Stripe, procesar el backend después de confirmar el pago
            await this._processStandardPayment();
        }
    }

    async _processWhopPayment() {
        // Acceder a WhopHandler desde la instancia global
        const whopHandler = window.checkoutApp?.modules?.whopHandler;

        if (!whopHandler) {
            throw new Error('Whop no está inicializado correctamente');
        }

        try {
            // Llamar al método submit del WhopHandler
            // Esto enviará el formulario embebido de Whop usando wco.submit()
            await whopHandler.submit();

            // Whop manejará la redirección automáticamente cuando el pago se complete
            // El postMessage handler en WhopHandler se encargará de ello
            // No llamamos a _processStandardPayment() aquí porque el webhook lo manejará

        } catch (error) {
            console.error('[AsyncPaymentProcessor] Whop error:', error);
            this._handleErrorResponse({
                success: false,
                error: error.message || 'Error procesando el pago con Whop',
                error_type: 'whop_payment_error',
                gateway_code: 'WHOP'
            });
        }
    }

    _captureFormData() {
        // Capturar todos los datos del formulario ANTES de que se deshabiliten los campos
        const formData = new FormData();

        // Obtener CSRF token
        const csrfInput = this.form.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput?.value) {
            formData.append('csrfmiddlewaretoken', csrfInput.value);
        }

        // Obtener gateway seleccionado
        const gatewayInput = this.form.querySelector('input[name="gateway_id"]:checked');
        if (gatewayInput?.value) {
            formData.append('gateway_id', gatewayInput.value);
        }

        // Obtener el número de teléfono completo (ya validado por intlTelInput)
        const phoneInput = this.form.querySelector('input[name="phone"]');
        if (phoneInput) {
            const iti = window.intlTelInputGlobals?.getInstance(phoneInput);
            if (iti) {
                const fullPhoneNumber = iti.getNumber(); // Formato: +34607465417
                if (fullPhoneNumber) {
                    formData.append('phone', fullPhoneNumber);
                }
            }
        }

        // Agregar todos los demás campos del formulario (NO filtrar por disabled todavía)
        const allInputs = this.form.querySelectorAll('input:not([type="radio"]):not([type="checkbox"]), select, textarea');
        allInputs.forEach(input => {
            if (input.name && input.value && !formData.has(input.name)) {
                formData.append(input.name, input.value);
            }
        });

        // Agregar radio buttons y checkboxes seleccionados
        const radioCheckboxInputs = this.form.querySelectorAll('input[type="radio"]:checked, input[type="checkbox"]:checked');
        radioCheckboxInputs.forEach(input => {
            if (input.name && !formData.has(input.name)) {
                formData.append(input.name, input.value);
            }
        });

        return formData;
    }

    async _processStandardPayment() {
        // Usar los datos del formulario capturados anteriormente
        const formData = this.capturedFormData || this._captureFormData();

        // Realizar petición asíncrona
        const response = await this._makePaymentRequest(formData);

        // Procesar respuesta
        if (response.success) {
            this._handleSuccessResponse(response);
        } else {
            this._handleErrorResponse(response);
        }
    }

    async _makePaymentRequest(formData) {

        // Obtener CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

        const response = await fetch(this.processUrl, {
            method: 'POST',
            body: formData,
            credentials: 'include',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
            }
        });

        const data = await response.json();

        // Agregar información de status HTTP a la respuesta
        data.httpStatus = response.status;
        data.httpStatusText = response.statusText;

        return data;
    }

    _handleSuccessResponse(response) {
        const { gateway_code, redirect_url, message, sale_uuid } = response;

        // Establecer URL de status para consultas futuras
        this.statusUrl = `${this.baseUrl}/c/api/status/${sale_uuid}/`;

        // Ocultar notificación de procesamiento
        this.notifications.hidePaymentProcessing();

        // Mostrar mensaje de éxito específico por gateway
        const successMessage = this._getSuccessMessage(gateway_code, message);
        this.notifications.showSuccess(successMessage);

        // Manejar redirección según el tipo de gateway
        this._handleRedirection(gateway_code, redirect_url, response);

        // Callback personalizado
        this.onSuccess(response);
    }

    _handleRedirection(gatewayCode, redirectUrl, response) {
        switch (gatewayCode) {
            case 'STRIPE':
                // Para Stripe, redirección directa a página de éxito
                this.notifications.showInfo('¡Pago exitoso! Redirigiendo...', { duration: 1000 });
                this._redirectWithDelay(redirectUrl, 1500);
                break;

            case 'DLOCAL':
                // Para dLocal, redirección a plataforma de pago
                this.notifications.showInfo('Redirigiendo a la plataforma de pago dLocal...', { duration: 800 });
                this._redirectWithDelay(redirectUrl, 1000);
                break;

            case 'BANK_TRANSFER':
                // Para transferencia bancaria, redirección a instrucciones
                this.notifications.showInfo('Redirigiendo a los detalles de transferencia...', { duration: 1200 });
                this._redirectWithDelay(redirectUrl, 1500);
                break;

            default:
                // Gateway desconocido - redirección genérica
                this.notifications.showInfo('Redirigiendo...', { duration: 800 });
                this._redirectWithDelay(redirectUrl, 1000);
        }
    }

    _handleErrorResponse(response) {
        const { error, error_type, gateway_code } = response;

        // Ocultar notificación de procesamiento
        this.notifications.hidePaymentProcessing();

        // Manejar errores específicos por gateway
        if (gateway_code && (error_type === 'payment_processing' || error_type === 'stripe_payment_error' || error_type === 'whop_payment_error')) {
            this.notifications.showGatewaySpecificError(gateway_code, error_type, error);
        } else {
            // Manejar diferentes tipos de errores genéricos
            switch (error_type) {
                case 'otp_validation':
                    this.notifications.showError('Error de verificación: ' + error);
                    this._focusPhoneField();
                    break;

                case 'gateway_validation':
                case 'gateway_not_found':
                    this.notifications.showError('Error de método de pago: ' + error);
                    this._focusGatewaySelection();
                    break;

                case 'validation_error':
                    this.notifications.showWarning('Error de validación: ' + error);
                    break;

                case 'network_error':
                    this.notifications.showGatewaySpecificError('GENERIC', 'network_error', error);
                    break;

                default:
                    this.notifications.showError(error || 'Error desconocido al procesar el pago');
            }
        }

        // Callback personalizado
        this.onError(response);
    }

    _handleNetworkError(error) {
        let errorMessage = 'Error de conexión. Por favor, verifica tu conexión a internet e inténtalo de nuevo.';

        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            errorMessage = 'No se pudo conectar con el servidor. Verifica tu conexión a internet.';
        } else if (error.name === 'AbortError') {
            errorMessage = 'La solicitud fue cancelada. Por favor, inténtalo de nuevo.';
        }

        this.notifications.showError(errorMessage);
        this.onError({ error: errorMessage, error_type: 'network_error' });
    }

    _redirectWithDelay(url, delay = 1000) {
        if (!url) {
            return;
        }

        setTimeout(() => {
            window.location.href = url;
        }, delay);
    }

    _focusPhoneField() {
        const phoneField = this.form.querySelector('#phone');
        if (phoneField) {
            phoneField.focus();
            phoneField.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    _focusGatewaySelection() {
        const gatewaySection = this.form.querySelector('.payment-methods, [name="gateway_id"]');
        if (gatewaySection) {
            gatewaySection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    _defaultSuccessHandler(response) {
        // Handler por defecto - puede ser sobrescrito
    }

    _defaultErrorHandler(response) {
        // Handler por defecto - puede ser sobrescrito
    }

    // Método público para consultar el estado de una venta
    async checkPaymentStatus(saleUuid) {
        if (!saleUuid && !this.statusUrl) {
            return null;
        }

        const url = saleUuid ? `${this.baseUrl}/c/api/status/${saleUuid}/` : this.statusUrl;

        try {
            const response = await fetch(url);
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    // Método para habilitar/deshabilitar el formulario durante el procesamiento
    setFormEnabled(enabled) {
        const submitButton = this.form.querySelector('button[type="submit"], input[type="submit"]');
        const inputs = this.form.querySelectorAll('input, select, textarea, button');

        inputs.forEach(input => {
            input.disabled = !enabled;
        });

        if (submitButton) {
            if (enabled) {
                submitButton.textContent = submitButton.dataset.originalText || 'Realizar Pedido';
                submitButton.classList.remove('cursor-not-allowed', 'opacity-75');
            } else {
                submitButton.dataset.originalText = submitButton.textContent;
                submitButton.textContent = 'Procesando...';
                submitButton.classList.add('cursor-not-allowed', 'opacity-75');
            }
        }
    }

    // ============ MÉTODOS AUXILIARES ============

    _getGatewayCode(paymentMethodCard) {
        if (!paymentMethodCard) return 'UNKNOWN';

        if (paymentMethodCard.querySelector('img[alt="Stripe"]')) return 'STRIPE';
        if (paymentMethodCard.querySelector('img[alt="Whop"]')) return 'WHOP';
        if (paymentMethodCard.querySelector('img[alt="dLocal"]')) return 'DLOCAL';
        if (paymentMethodCard.textContent.includes('Transferencia') ||
            paymentMethodCard.textContent.includes('Bank')) return 'BANK_TRANSFER';

        return 'UNKNOWN';
    }

    _getSuccessMessage(gatewayCode, originalMessage) {
        const successMessages = {
            'STRIPE': '¡Pago con tarjeta exitoso!',
            'WHOP': '¡Pago procesado exitosamente!',
            'DLOCAL': '¡Pedido creado! Serás redirigido para completar el pago.',
            'BANK_TRANSFER': '¡Pedido creado! Te mostraremos los datos para la transferencia.',
            'UNKNOWN': '¡Pedido procesado exitosamente!'
        };

        return successMessages[gatewayCode] || originalMessage || successMessages['UNKNOWN'];
    }

    /**
     * Extrae billing_details del formulario para enviar a Stripe.
     * Esto mejora la tasa de aceptación de pagos al proporcionar
     * información de verificación AVS (Address Verification System).
     */
    _getBillingDetails() {
        const firstName = this.form.querySelector('#first_name')?.value || '';
        const lastName = this.form.querySelector('#last_name')?.value || '';
        const email = this.form.querySelector('#email')?.value || '';
        const address = this.form.querySelector('#address')?.value || '';
        const countryCode = this.form.querySelector('input[name="country_code"]')?.value || '';

        // Obtener teléfono completo desde intlTelInput
        let phone = '';
        const phoneInput = this.form.querySelector('#phone');
        if (phoneInput) {
            const iti = window.intlTelInputGlobals?.getInstance(phoneInput);
            phone = iti ? iti.getNumber() : phoneInput.value;
        }

        const billingDetails = {
            name: `${firstName} ${lastName}`.trim(),
            email: email,
            phone: phone,
            address: {
                line1: address,
                country: countryCode.toUpperCase()
            }
        };

        // Limpiar campos vacíos para evitar errores de validación en Stripe
        if (!billingDetails.name) delete billingDetails.name;
        if (!billingDetails.email) delete billingDetails.email;
        if (!billingDetails.phone) delete billingDetails.phone;
        if (!billingDetails.address.line1) delete billingDetails.address.line1;
        if (!billingDetails.address.country) delete billingDetails.address.country;
        if (Object.keys(billingDetails.address).length === 0) delete billingDetails.address;

        return billingDetails;
    }

    _getBaseUrl() {
        const isProduction = document.body.dataset.production === 'true';
        return isProduction ? 'https://crm.conquerx.com' : '';
    }
}
