/**
 * Coordinador principal del checkout
 * Responsabilidad única: Orquestar todos los módulos del checkout
 */
import { NotificationManager } from './utils/notifications.js';
import { ModalManager } from './utils/modal-manager.js';
import { CheckoutState } from './utils/checkout-state.js';
import { PhoneValidator } from './modules/phone-validator.js';
import { OTPSystem } from './modules/otp-system.js';
import { AsyncPaymentProcessor } from './modules/async-payment-processor.js';
import { WhopHandler } from './modules/whop-handler.js?v=1.1.4-clarity-hosted-checkout';
import { StripeHandler } from './modules/stripe-handler.js';

class CheckoutApp {
  constructor() {
    console.log('[CheckoutMain] loaded v1.1.4-clarity-hosted-checkout');
    this.modules = {};
    this.state = new CheckoutState();
    this.notifications = new NotificationManager();

    this._initializeModules();
    this._bindEvents();
    this._setupInterModuleCommunication();
  }

  _initializeModules() {
    // Modales
    this.modules.otpModal = new ModalManager('phone-verification-modal');
    this.modules.termsModal = new ModalManager('terms-modal');
    this.modules.processingModal = new ModalManager('processing-modal', { closeOnOutside: false, closeOnEscape: false });

    // Validador de teléfono
    this.modules.phoneValidator = new PhoneValidator('phone');

    // Sistema OTP
    this.modules.otpSystem = new OTPSystem(this.modules.otpModal, {
      shortCode: document.body.dataset.shortCode
    });

    // Configurar callback para resetear el modal OTP cuando se cierre
    this.modules.otpModal.onHide(() => {
      this.modules.otpSystem.resetModal();
    });

    // Procesador de pagos asíncrono
    const checkoutForm = document.getElementById('checkout-form');
    if (checkoutForm) {
      this.modules.paymentProcessor = new AsyncPaymentProcessor(checkoutForm, {
        shortCode: document.body.dataset.shortCode,
        onProcessingStart: () => this._onPaymentProcessingStart(),
        onProcessingEnd: () => this._onPaymentProcessingEnd(),
        onSuccess: (response) => this._onPaymentSuccess(response),
        onError: (response) => this._onPaymentError(response)
      });
    }

    // Stripe (crear PaymentIntent bajo demanda cuando se selecciona - igual que Whop)
    const stripeKey = document.body.dataset.stripeKey;
    if (stripeKey && window.Stripe) {
      try {
        this.modules.stripeHandler = new StripeHandler({
          shortCode: document.body.dataset.shortCode,
          orderUuid: document.body.dataset.orderUuid,
          stripeKey: stripeKey,
          onReady: () => this._onStripeReady(),
          onError: (error) => this._onStripeError(error)
        });
      } catch (error) {
        this.modules.stripeHandler = null;
      }
    }

    // Whop (crear PaymentIntent bajo demanda cuando se selecciona)
    const isDualStep2 = document.body.dataset.isDualPayment === 'true' &&
                        document.body.dataset.dualActiveSegmentOrder === '2';
    try {
      this.modules.whopHandler = new WhopHandler({
        shortCode: document.body.dataset.shortCode,
        orderUuid: document.body.dataset.orderUuid,
        isDualPaymentStep2: isDualStep2,
        onReady: () => this._onWhopReady(),
        onError: (error) => this._onWhopError(error)
      });
    } catch (error) {
      this.modules.whopHandler = null;
    }

    // Dual Payment paso 2: auto-inicializar Whop embed
    if (isDualStep2) {
      this._toggleWhopElements(true);
    }
  }

  _bindEvents() {
    // Evento del formulario
    const submitButton = document.getElementById('submit-button');
    const termsCheckbox = document.getElementById('terms-checkbox');
    const termsLink = document.getElementById('terms-link');

    // Submit del formulario - ahora delegado al AsyncPaymentProcessor
    // El procesador maneja automáticamente la validación y el envío
    submitButton?.addEventListener('click', (e) => this._handleFormSubmit(e));

    // Términos y condiciones
    termsCheckbox?.addEventListener('change', (e) => {
      this._handleTermsChange(e);
    });

    // Ocultar loader de términos después de registrar el evento crítico del checkbox
    this._hideTermsLoadingOverlay();

    termsLink?.addEventListener('click', (e) => {
      e.preventDefault();
      this._showTermsModal();
    });

    // Payment method cards
    this._initPaymentMethodCards();

    // Botones de modales
    document.getElementById('accept-terms')?.addEventListener('click', () => {
      this._acceptTerms();
    });

    // Stripe elements
    this._setupStripeElements();
  }

  _initPaymentMethodCards() {
    const paymentCards = document.querySelectorAll('.payment-method-card');

    paymentCards.forEach(card => {
      card.addEventListener('click', () => {
        const gatewayId = card.dataset.gateway;
        this._selectPaymentMethod(gatewayId);
      });
    });

    // Select default payment method (Whop first, then Stripe if Whop not available)
    const whopImg = document.querySelector('img[alt="Whop"]');
    const whopCard = whopImg ? whopImg.closest('.payment-method-card') : null;

    if (whopCard) {
      const gatewayId = whopCard.dataset.gateway;
      this._selectPaymentMethod(gatewayId);
    } else {
      // Fallback to Stripe if Whop is not available
      const stripeImg = document.querySelector('img[alt="Stripe"]');
      const stripeCard = stripeImg ? stripeImg.closest('.payment-method-card') : null;
      if (stripeCard) {
        const gatewayId = stripeCard.dataset.gateway;
        this._selectPaymentMethod(gatewayId);
      }
    }
  }

  _selectPaymentMethod(gatewayId) {
    // Remove selected class from all cards
    document.querySelectorAll('.payment-method-card').forEach(card => {
      card.classList.remove('selected');
    });

    // Add selected class to clicked card
    const selectedCard = document.querySelector(`[data-gateway="${gatewayId}"]`);
    if (selectedCard) {
      selectedCard.classList.add('selected');
    }

    // Update radio button
    const radioButton = document.getElementById(`gateway-${gatewayId}`);
    if (radioButton) {
      radioButton.checked = true;
    }

    // Check which gateway was selected
    const paymentMethodCard = document.querySelector(`[data-gateway="${gatewayId}"]`);
    const isStripe = paymentMethodCard && paymentMethodCard.querySelector('img[alt="Stripe"]') !== null;
    const isWhop = paymentMethodCard && paymentMethodCard.querySelector('img[alt="Whop"]') !== null;

    this.state.updateGatewaySelection(gatewayId, isStripe);

    // Show/hide Stripe elements container
    this._toggleStripeElements(isStripe);

    // Show/hide Whop elements container and initialize if needed
    this._toggleWhopElements(isWhop);
  }

  _toggleStripeElements(isStripe) {
    const stripeContainer = document.getElementById('stripe-elements-container');

    if (stripeContainer) {
      if (isStripe) {
        // Expand with animation
        stripeContainer.style.maxHeight = '2000px';
        stripeContainer.style.opacity = '1';
        this._initializeStripeCheckout();
      } else {
        // Collapse with animation
        stripeContainer.style.maxHeight = '0';
        stripeContainer.style.opacity = '0';
      }
    }
  }

  async _initializeStripeCheckout() {
    if (!this.modules.stripeHandler) {
      return;
    }

    // Si ya está listo, no hacer nada
    if (this.modules.stripeHandler.isReady()) {
      return;
    }

    // Mostrar loading mientras se inicializa
    const stripeContainer = document.getElementById('stripe-payment-element');
    if (stripeContainer) {
      stripeContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-8">
          <div class="relative">
            <div class="w-12 h-12 border-4 border-gray-200 rounded-full"></div>
            <div class="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin absolute top-0 left-0"></div>
          </div>
          <p class="text-sm text-gray-600 mt-3 font-medium">Cargando checkout de Stripe...</p>
        </div>
      `;
    }

    try {
      await this.modules.stripeHandler.initialize();
      // Actualizar referencias para compatibilidad con AsyncPaymentProcessor
      this.stripe = this.modules.stripeHandler.getStripe();
      this.stripeElements = this.modules.stripeHandler.getElements();
    } catch (error) {
      if (stripeContainer) {
        stripeContainer.innerHTML = `
          <div class="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 text-sm">
            <p class="font-medium">Error cargando checkout de Stripe</p>
            <p class="mt-1">${error.message || 'Por favor, intenta de nuevo o selecciona otro método de pago.'}</p>
          </div>
        `;
      }
    }
  }

  _onStripeReady() {
    // El checkout de Stripe está listo para procesar el pago
  }

  _onStripeError(error) {
    this.notifications.show(
      error || 'Error con el checkout de Stripe',
      'error',
      5000
    );
  }

  _setupStripeElements() {
    // Mount Stripe elements if Stripe is already selected (inicialización bajo demanda)
    setTimeout(() => {
      const selectedGateway = document.querySelector('input[name="gateway_id"]:checked');
      if (selectedGateway) {
        const gatewayId = selectedGateway.value;
        const paymentMethodCard = document.querySelector(`[data-gateway="${gatewayId}"]`);
        const isStripe = paymentMethodCard && paymentMethodCard.querySelector('img[alt="Stripe"]') !== null;

        if (isStripe) {
          this.state.updateGatewaySelection(gatewayId, true);
          this._toggleStripeElements(true);
        }
      }
    }, 100);
  }

  // === WHOP METHODS ===

  _toggleWhopElements(isWhop) {
    const whopContainer = document.getElementById('whop-elements-container');

    if (whopContainer) {
      if (isWhop) {
        // Expand with animation
        whopContainer.style.maxHeight = '2000px';
        whopContainer.style.opacity = '1';
        this._initializeWhopCheckout();
      } else {
        // Collapse with animation
        whopContainer.style.maxHeight = '0';
        whopContainer.style.opacity = '0';
        // No destruir Whop handler para preservar el estado del embed
        // if (this.modules.whopHandler) {
        //   this.modules.whopHandler.destroy();
        // }
      }
    }
  }

  async _initializeWhopCheckout() {
    if (!this.modules.whopHandler) {
      return;
    }

    // Si ya está listo, no hacer nada (el embed ya está en el DOM)
    if (this.modules.whopHandler.isReady()) {
      return;
    }

    // Mostrar loading mientras se inicializa
    const whopContainer = document.getElementById('whop-checkout-container');
    if (whopContainer) {
      whopContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-8">
          <div class="relative">
            <div class="w-12 h-12 border-4 border-gray-200 rounded-full"></div>
            <div class="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin absolute top-0 left-0"></div>
          </div>
          <p class="text-sm text-gray-600 mt-3 font-medium">Cargando checkout de Whop...</p>
        </div>
      `;
    }

    try {
      await this.modules.whopHandler.initialize();
    } catch (error) {
      if (whopContainer) {
        whopContainer.innerHTML = `
          <div class="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 text-sm">
            <p class="font-medium">Error cargando checkout de Whop</p>
            <p class="mt-1">${error.message || 'Por favor, intenta de nuevo o selecciona otro método de pago.'}</p>
          </div>
        `;
      }
    }
  }

  _onWhopReady() {
    // El checkout de Whop está listo para procesar el pago
  }

  _onWhopError(error) {
    this.notifications.show(
      error || 'Error con el checkout de Whop',
      'error',
      5000
    );
  }

  // === END WHOP METHODS ===

  _setupInterModuleCommunication() {
    // Phone Validator callbacks
    this.modules.phoneValidator.onValidated((isValid, phoneNumber) => {
      this.state.updatePhoneState(isValid, phoneNumber);

      if (isValid) {
        this.modules.otpSystem.updateModalPhone(phoneNumber);
      }
    });

    this.modules.phoneValidator.onChanged((phoneNumber) => {
      this.modules.otpSystem.checkPhoneChange(phoneNumber);
    });

    // OTP System callbacks
    this.modules.otpSystem.onVerified((phoneNumber) => {
      this.state.updateOTPVerification(true, phoneNumber);
      this.notifications.show('Teléfono verificado correctamente', 'info');
    });

    this.modules.otpSystem.onPhoneChanged(() => {
      this.notifications.show('Has cambiado tu número de teléfono. Debes verificarlo nuevamente.', 'info');
    });
  }

  _handleFormSubmit(e) {
    e.preventDefault();

    const submitState = this.state.canSubmitForm();
    if (!submitState.canSubmit) {
      this._handleSubmitBlocked(submitState.reason);
      return;
    }

    // Dual Payment paso 1: redirect en vez de submit
    if (document.body.dataset.isDualPayment === 'true' &&
        document.body.dataset.dualActiveSegmentOrder === '1') {
      this._handleDualStep1Redirect();
      return;
    }

    // Delegar al AsyncPaymentProcessor - maneja toda la lógica de pagos
    this.modules.paymentProcessor?.processPayment();
  }

  async _handleDualStep1Redirect() {
    const submitButton = document.getElementById('submit-button');
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = 'Redirigiendo...';
      submitButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
      submitButton.classList.add('bg-blue-400', 'opacity-75');
    }

    try {
      const saleUuid = document.body.dataset.orderUuid;
      const response = await fetch('/c/api/dual-payment/create-checkout/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sale_uuid: saleUuid })
      });
      const data = await response.json();

      if (!data.success) {
        this.notifications.show(data.error || 'Error al crear el checkout', 'error');
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = 'Reintentar';
          submitButton.classList.remove('bg-blue-400', 'opacity-75');
          submitButton.classList.add('bg-blue-600');
        }
        return;
      }

      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        this.notifications.show('No se pudo obtener la URL de checkout', 'error');
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = 'Reintentar';
        }
      }
    } catch (err) {
      console.error('[DualPayment] Redirect error:', err);
      this.notifications.show('Error de conexión. Intenta de nuevo.', 'error');
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = 'Reintentar';
      }
    }
  }

  _handleSubmitBlocked(reason) {
    switch (reason) {
      case 'terms_required':
        this.notifications.show('Debes aceptar los términos y condiciones para continuar.', 'error');
        break;
      case 'phone_invalid':
        this.notifications.show('Por favor, verifica que tu número de teléfono sea válido.', 'error');
        this.modules.phoneValidator.focus();
        break;
      case 'otp_required':
        if (this.state.needsOTPVerification()) {
          this.modules.otpModal.show();
        } else {
          this.notifications.show('Por favor, ingresa un número de teléfono válido antes de continuar.', 'error');
          this.modules.phoneValidator.focus();
        }
        break;
    }
  }




  _handleTermsChange(e) {
    const accepted = e.target.checked;
    const otpVerificationEnabled = document.body.dataset.checkoutOtpVerificationEnabled === 'true';

    // Si el usuario intenta aceptar términos, debe verificar OTP primero (si está habilitado)
    if (accepted) {
      // Primero verificar que el teléfono sea válido
      if (!this.state.isPhoneValid()) {
        e.preventDefault();
        e.target.checked = false;
        this.notifications.show('Por favor, ingresa un número de teléfono válido antes de continuar.', 'error');
        this.modules.phoneValidator.focus();
        return;
      }

      // Luego verificar si necesita OTP (si la verificación está habilitada)
      if (otpVerificationEnabled && !this.state.isOTPVerified()) {
        e.preventDefault();
        e.target.checked = false;
        this.modules.otpModal.show();
        return;
      }
    }

    this.state.updateTermsAcceptance(accepted);
  }

  async _showTermsModal() {
    this.modules.termsModal.show();
    await this._loadTermsContent();
  }

  async _loadTermsContent() {
    const termsContent = document.getElementById('terms-content');
    if (!termsContent) return;

    try {
      termsContent.innerHTML = '<p class="text-gray-600 italic">Cargando términos y condiciones...</p>';

      const shortCode = document.body.dataset.shortCode;
      const baseUrl = this._getBaseUrl();
      const response = await fetch(`${baseUrl}/terms-and-conditions/${shortCode}/`);
      const data = await response.json();

      if (data.success) {
        termsContent.innerHTML = data.content;
      } else {
        termsContent.innerHTML = '<p class="text-red-600">Error al cargar los términos.</p>';
      }
    } catch (error) {
      termsContent.innerHTML = '<p class="text-red-600">Error de conexión.</p>';
    }
  }

  _acceptTerms() {
    const termsCheckbox = document.getElementById('terms-checkbox');
    if (termsCheckbox) {
      termsCheckbox.checked = true;
      this.state.updateTermsAcceptance(true);
    }
    this.modules.termsModal.hide();
  }

  // ============ CALLBACKS PARA PROCESAMIENTO ASÍNCRONO ============

  _onPaymentProcessingStart() {
    this.paymentFailed = false;

    // Mostrar modal de procesamiento
    this.modules.processingModal.show();

    // Deshabilitar formulario
    if (this.modules.paymentProcessor) {
      this.modules.paymentProcessor.setFormEnabled(false);
    }

    // Ocultar notificaciones previas
    this.notifications.hideAll();
  }

  _onPaymentProcessingEnd() {
    const whopContainer = document.getElementById('whop-elements-container');
    const isWhopSelected = whopContainer && whopContainer.style.opacity === '1';

    const hideModal = () => {
      // Ocultar modal de procesamiento
      this.modules.processingModal.hide();

      // Habilitar formulario
      if (this.modules.paymentProcessor) {
        this.modules.paymentProcessor.setFormEnabled(true);
      }
    };

    // Si es Whop y no hubo error, esperar 5 segundos antes de cerrar el modal
    // para dar tiempo a que Whop redirija o reaccione
    if (isWhopSelected && !this.paymentFailed) {
      setTimeout(hideModal, 5000);
    } else {
      hideModal();
    }
  }

  _onPaymentSuccess(response) {

    // El AsyncPaymentProcessor ya maneja la redirección automáticamente
    // Aquí podemos agregar lógica adicional si es necesaria

    // Ejemplo: tracking de conversión
    if (window.gtag && response.sale_uuid) {
      gtag('event', 'purchase', {
        'transaction_id': response.sale_uuid,
        'value': response.amount || 0,
        'currency': response.currency || 'EUR'
      });
    }
  }

  _onPaymentError(response) {
    this.paymentFailed = true;

    // El AsyncPaymentProcessor ya maneja la mostración de errores
    // Aquí podemos agregar lógica adicional de recuperación

    // Enfocar campos específicos según el tipo de error
    switch (response.error_type) {
      case 'otp_validation':
        this.modules.phoneValidator.focus();
        break;
      case 'gateway_validation':
        // Hacer scroll a la sección de métodos de pago
        const paymentSection = document.querySelector('.payment-methods');
        if (paymentSection) {
          paymentSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        break;
      case 'payment_processing':
        // Para errores de procesamiento, mantener el foco en el botón submit
        const submitButton = document.getElementById('submit-button');
        if (submitButton) {
          submitButton.focus();
        }
        break;
    }
  }

  _getBaseUrl() {
    const isProduction = document.body.dataset.production === 'true';
    return isProduction ? 'https://crm.conquerx.com' : '';
  }

  _hideTermsLoadingOverlay() {
    // Ocultar el overlay de carga de términos después de registrar los eventos
    const termsLoadingOverlay = document.getElementById('terms-loading-overlay');
    const termsContentWrapper = document.getElementById('terms-content-wrapper');

    if (termsLoadingOverlay && termsContentWrapper) {
      // Habilitar interacción con el contenido
      termsContentWrapper.classList.remove('pointer-events-none');

      // Agregar transición suave
      termsLoadingOverlay.style.opacity = '0';
      termsLoadingOverlay.style.transition = 'opacity 0.3s ease-out';

      termsContentWrapper.style.opacity = '1';
      termsContentWrapper.style.transition = 'opacity 0.3s ease-out';

      // Remover el overlay del DOM después de la transición
      setTimeout(() => {
        termsLoadingOverlay.remove();
      }, 300);
    }
  }
}

// Global function for payment method selection (called from template)
window.selectPaymentMethod = function (gatewayId) {
  if (window.checkoutApp) {
    window.checkoutApp._selectPaymentMethod(gatewayId);
  }
};

// Inicializar la aplicación inmediatamente
// Los módulos ya se cargan después de que el DOM esté listo
window.checkoutApp = new CheckoutApp();
