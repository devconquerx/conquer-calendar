/**
 * StripeHandler - Maneja la integración con Stripe Elements
 * Responsabilidad: Crear PaymentIntent bajo demanda y cargar Stripe Elements
 * Patrón: Igual que WhopHandler - inicialización lazy cuando se selecciona el método
 */

export class StripeHandler {
  constructor(options = {}) {
    this.shortCode = options.shortCode;
    this.orderUuid = options.orderUuid;
    this.stripeKey = options.stripeKey;
    this.clientSecret = null;  // Se obtendrá bajo demanda al inicializar
    this.onReady = options.onReady || (() => {});
    this.onError = options.onError || (() => {});

    this.isInitialized = false;
    this.isLoading = false;
    this.stripe = null;
    this.stripeElements = null;
    this.paymentElement = null;
  }

  /**
   * Inicializa Stripe cuando el usuario selecciona este método de pago
   */
  async initialize() {
    if (this.isInitialized || this.isLoading) {
      return;
    }

    this.isLoading = true;

    try {
      // Paso 1: Crear PaymentIntent bajo demanda (solo al seleccionar Stripe)
      if (!this.clientSecret) {
        await this._createPaymentIntent();
      }

      // Paso 2: Inicializar Stripe con el client_secret
      this._initializeStripeElements();

      // Paso 3: Montar el Payment Element
      this._mountPaymentElement();

      this.isInitialized = true;
      this.isLoading = false;

      this.onReady();

    } catch (error) {
      console.error('[STRIPE] Error initializing:', error);
      this.isLoading = false;
      this.onError(error.message || 'Error inicializando Stripe');
    }
  }

  /**
   * Crea el PaymentIntent de Stripe bajo demanda
   * @returns {Promise<void>}
   */
  async _createPaymentIntent() {
    try {
      const url = `/c/api/${this.shortCode}/create-stripe-intent/`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          order_uuid: this.orderUuid
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Error creando PaymentIntent de Stripe');
      }

      const data = await response.json();

      if (!data.success || !data.client_secret) {
        throw new Error('No se recibió client_secret del servidor');
      }

      this.clientSecret = data.client_secret;

    } catch (error) {
      console.error('[STRIPE] Error creating PaymentIntent:', error);
      throw error;
    }
  }

  /**
   * Inicializa Stripe Elements con el client_secret
   */
  _initializeStripeElements() {
    if (!window.Stripe) {
      throw new Error('Stripe.js no está cargado');
    }

    this.stripe = Stripe(this.stripeKey);

    this.stripeElements = this.stripe.elements({
      clientSecret: this.clientSecret,
      appearance: {
        theme: 'stripe',
        variables: {
          colorPrimary: '#3b82f6',
          colorBackground: '#ffffff',
          colorText: '#374151',
          colorDanger: '#ef4444',
          fontFamily: 'system-ui, sans-serif',
        }
      }
    });
  }

  /**
   * Monta el Payment Element en el contenedor
   */
  _mountPaymentElement() {
    const container = document.getElementById('stripe-payment-element');

    if (!container) {
      throw new Error('Contenedor de Stripe no encontrado en el DOM');
    }

    // Limpiar contenedor antes de montar
    container.innerHTML = '';

    try {
      // Crear Payment Element con configuración para desactivar wallets
      this.paymentElement = this.stripeElements.create('payment', {
        wallets: {
          applePay: 'never',
          googlePay: 'never',
          link: 'never'
        }
      });

      this.paymentElement.mount('#stripe-payment-element');

      // Escuchar cambios para mostrar errores
      this.paymentElement.on('change', (event) => {
        this._handleElementChange(event);
      });

    } catch (error) {
      console.error('[STRIPE] Error mounting payment element:', error);
      throw error;
    }
  }

  /**
   * Maneja cambios en el Payment Element
   */
  _handleElementChange(event) {
    const errorsElement = document.getElementById('stripe-errors');

    if (errorsElement) {
      if (event.error) {
        errorsElement.textContent = event.error.message;
        errorsElement.classList.remove('hidden');
      } else {
        errorsElement.textContent = '';
        errorsElement.classList.add('hidden');
      }
    }
  }

  /**
   * Limpia recursos cuando se cambia de método de pago
   */
  destroy() {
    if (this.paymentElement) {
      this.paymentElement.unmount();
      this.paymentElement = null;
    }

    this.isInitialized = false;
    this.isLoading = false;
  }

  /**
   * Verifica si Stripe está listo para procesar el pago
   */
  isReady() {
    return this.isInitialized && this.clientSecret !== null && this.stripe !== null;
  }

  /**
   * Obtiene el objeto Stripe para usar en el procesamiento del pago
   */
  getStripe() {
    return this.stripe;
  }

  /**
   * Obtiene los Elements para usar en el procesamiento del pago
   */
  getElements() {
    return this.stripeElements;
  }
}
