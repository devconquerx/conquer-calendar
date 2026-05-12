/**
 * WhopHandler - Maneja la integración con Whop Embedded Checkout
 * Responsabilidad: Usar plan_id pre-creado y cargar checkout embebido
 */

export class WhopHandler {
  constructor(options = {}) {
    console.log('[WhopHandler] loaded redirect-debug');
    this.shortCode = options.shortCode;
    this.orderUuid = options.orderUuid;
    this.isDualPaymentStep2 = options.isDualPaymentStep2 || false;
    this.whopSessionId = null;  // Se obtendrá bajo demanda al inicializar (ahora es session, no plan)
    this.checkoutUrl = null;
    this.onReady = options.onReady || (() => {});
    this.onError = options.onError || (() => {});

    this.isInitialized = false;
    this.isLoading = false;
    this.loaderScriptLoaded = false;
    this.embedId = 'whop-embedded-checkout';  // ID único para el embed
    this.checkoutStatusPoll = null;

    // Para manejar la promesa del submit
    this.submitResolve = null;
    this.submitReject = null;
  }

  /**
   * Inicializa Whop cuando el usuario selecciona este método de pago
   */
  async initialize() {
    console.log('[WhopHandler] initialize', {
      shortCode: this.shortCode,
      orderUuid: this.orderUuid,
      isDualPaymentStep2: this.isDualPaymentStep2,
      allowSplitit: document.body.dataset.allowSplitit,
    });
    if (this.isInitialized || this.isLoading) {
      return;
    }

    this.isLoading = true;

    try {
      if (await this._handleRedirectReturn()) {
        this.isInitialized = true;
        this.isLoading = false;
        this.onReady();
        return;
      }

      // Paso 1: Crear checkout session bajo demanda (solo al seleccionar Whop)
      if (!this.whopSessionId) {
        await this._createPaymentIntent();
      }

      // Paso 2: Cargar el loader script de Whop (solo si no está cargado)
      await this._loadWhopLoader();

      // Paso 3: Montar el checkout embebido de Whop
      this._mountWhopCheckout();

      this.isInitialized = true;
      this.isLoading = false;

      this.onReady();

    } catch (error) {
      console.error('[WHOP] Error initializing:', error);
      this.isLoading = false;
      this.onError(error.message || 'Error inicializando Whop');
    }
  }

  /**
   * Crea el checkout session de Whop bajo demanda
   * @returns {Promise<void>}
   */
  async _createPaymentIntent() {
    try {
      let url, bodyData;

      if (this.isDualPaymentStep2) {
        // Dual payment paso 2: usar endpoint de dual payment
        url = `/c/api/dual-payment/create-checkout/`;
        bodyData = { sale_uuid: this.orderUuid };
      } else {
        // Flujo normal
        url = `/c/api/${this.shortCode}/create-whop-intent/`;
        bodyData = { order_uuid: this.orderUuid };
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(bodyData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Error creando checkout de Whop');
      }

      const data = await response.json();
      console.log('[WhopHandler] createPaymentIntent response', data);

      // El backend ahora devuelve session_id (via plan_id por compatibilidad)
      // El backend devuelve session_id como plan_id (normal) o session_id (dual payment)
      const sessionId = data.plan_id || data.session_id;
      if (!data.success || !sessionId) {
        throw new Error('No se recibió session_id del servidor');
      }

      this.whopSessionId = sessionId;
      this.checkoutUrl = data.checkout_url || null;

    } catch (error) {
      console.error('[WHOP] Error creating checkout session:', error);
      throw error;
    }
  }

  /**
   * Carga el loader script de Whop dinámicamente si no está ya cargado
   * @returns {Promise<void>}
   */
  async _loadWhopLoader() {
    // Verificar si ya está cargado
    if (this.loaderScriptLoaded || document.querySelector('script[src="https://js.whop.com/static/checkout/loader.js"]')) {
      this.loaderScriptLoaded = true;
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://js.whop.com/static/checkout/loader.js';
      script.async = true;
      script.defer = true;

      script.onload = () => {
        this.loaderScriptLoaded = true;
        resolve();
      };

      script.onerror = () => {
        const error = 'Error cargando loader script de Whop';
        console.error('[WHOP]', error);
        reject(new Error(error));
      };

      document.body.appendChild(script);
    });
  }

  /**
   * Monta el checkout embebido de Whop en el contenedor
   */
  _mountWhopCheckout() {
    const container = document.getElementById('whop-checkout-container');

    if (!container) {
      throw new Error('Contenedor de Whop no encontrado en el DOM');
    }

    try {
      // Limpiar contenedor antes de montar
      container.innerHTML = '';

      const isSplitit = document.body.dataset.allowSplitit === 'true';
      if (isSplitit) {
        container.classList.remove('min-h-[400px]');
        container.innerHTML = `
          <div class="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-4 text-sm">
            <p class="font-medium">Checkout externo de Whop</p>
            <p class="mt-1">Para financieras USA seras redirigido al checkout hosteado de Whop al continuar.</p>
          </div>
        `;
        console.log('[WhopHandler] hosted checkout mode', {
          checkoutUrl: this.checkoutUrl,
          sessionId: this.whopSessionId,
        });
        return;
      }

      container.classList.add('min-h-[400px]');

      // Crear el div con atributos data- que Whop usa para el embed
      const embedDiv = document.createElement('div');
      embedDiv.id = this.embedId;  // ID único requerido para submit programático
      // Usar session en lugar de plan_id para aplicar payment_method_configuration
      embedDiv.setAttribute('data-whop-checkout-session', this.whopSessionId);
      embedDiv.setAttribute('data-whop-checkout-theme', 'light');
      embedDiv.setAttribute('data-whop-checkout-hide-submit-button', 'true');
      // Sandbox mode: el embed necesita saber que apunta al entorno de pruebas
      if (document.body.dataset.whopSandbox === 'true') {
        embedDiv.setAttribute('data-whop-checkout-environment', 'sandbox');
      }
      // No usar setup-future-usage para Splitit: Splitit no soporta off_session y Whop lo filtraría
      embedDiv.setAttribute('data-whop-checkout-skip-redirect', 'true');

      console.log('[WhopHandler] mount checkout', {
        sessionId: this.whopSessionId,
        isSplitit,
        returnUrl: null,
        skipRedirect: true,
      });

      embedDiv.setAttribute('data-whop-checkout-setup-future-usage', 'off_session');
      // embedDiv.setAttribute('data-whop-checkout-theme-accent-color', '#your-brand-color');  // Opcional: color de acento
      embedDiv.className = 'whop-checkout-embed';

      // Prellenar datos del cliente si están disponibles
      const customerEmail = document.body.dataset.customerEmail;
      const customerName = document.body.dataset.customerName?.trim();
      const customerAddress = document.body.dataset.customerAddress;
      const customerCity = document.body.dataset.customerCity;
      const customerCountryCode = document.body.dataset.customerCountryCode;

      // Agregar atributos de prefill solo si los datos están disponibles
      if (customerEmail) {
        embedDiv.setAttribute('data-whop-checkout-prefill-email', customerEmail);
      }

      if (customerName) {
        embedDiv.setAttribute('data-whop-checkout-prefill-name', customerName);
      }

      // Prellenar dirección (campos visibles para que el usuario complete state/postal)
      if (customerAddress) {
        embedDiv.setAttribute('data-whop-checkout-prefill-address-line1', customerAddress);
      }

      if (customerCity) {
        embedDiv.setAttribute('data-whop-checkout-prefill-address-city', customerCity);
      }

      if (customerCountryCode) {
        embedDiv.setAttribute('data-whop-checkout-prefill-address-country', customerCountryCode);
      }

      container.appendChild(embedDiv);

      // Escuchar mensajes de Whop para detectar cuando se completa el pago
      this._setupMessageListener();

      // Si el script ya estaba cargado, reinicializar los embeds
      if (this.loaderScriptLoaded) {
        // Recargar el script para que detecte el nuevo embed
        const newScript = document.createElement('script');
        newScript.src = 'https://js.whop.com/static/checkout/loader.js';
        newScript.async = true;
        newScript.defer = true;
        document.body.appendChild(newScript);
      }

    } catch (error) {
      console.error('[WHOP] Error mounting checkout:', error);
      throw error;
    }
  }

  /**
   * Configura listener para mensajes postMessage de Whop
   */
  _setupMessageListener() {
    if (this.messageListenerSetup) {
      return;
    }

    // IMPORTANTE: Capturar TODOS los mensajes para debugging
    window.addEventListener('message', (event) => {
      // Solo procesar mensajes de Whop
      if (!event.origin.includes('whop')) {
        return;
      }

      // Eventos posibles de completación
      const possibleCompletionEvents = [
        'whop-checkout-complete',
        'checkout-complete',
        'payment-complete',
        'purchase-complete',
        'checkout.complete',
        'checkout:complete',
        'complete',
        'success',
        'payment.succeeded'
      ];

      // Eventos posibles de error
      const possibleErrorEvents = [
        'address-validation-error',
        'payment-error',
        'checkout-error',
        'validation-error',
        'error',
        'fail',
        'failed'
      ];

      if (event.data && typeof event.data === 'object') {
        const eventType = event.data.type || event.data.event || event.data.action || event.data.status;

        // Verificar si es un evento de error
        if (possibleErrorEvents.includes(eventType) ||
            (eventType && eventType.includes('error')) ||
            (eventType && eventType.includes('fail')) ||
            (eventType && eventType.includes('validation'))) {

          this._handleWhopError(event.data);
        }
        // Verificar si es un evento de completación
        else if (possibleCompletionEvents.includes(eventType) ||
            (eventType && eventType.includes('complete')) ||
            (eventType && eventType.includes('success')) ||
            (eventType && eventType.includes('succeeded'))) {

          this._handleWhopSuccess(event.data);
        }
      }
      // Si el mensaje es un string, también procesarlo
      else if (typeof event.data === 'string') {
        const lowerData = event.data.toLowerCase();
        if (lowerData.includes('complete') || lowerData.includes('success')) {
          this._handleWhopSuccess({ message: event.data });
        } else if (lowerData.includes('error') || lowerData.includes('fail')) {
          this._handleWhopError({ message: event.data });
        }
      }
    });

    this.messageListenerSetup = true;
  }

  async _handleRedirectReturn() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const isSplitit = document.body.dataset.allowSplitit === 'true';

    console.log('[WhopHandler] handleRedirectReturn', {
      status,
      isSplitit,
      search: window.location.search,
    });

    if (!isSplitit || !status) {
      return false;
    }

    const container = document.getElementById('whop-checkout-container');
    if (!container) {
      return false;
    }

    if (status === 'error') {
      container.innerHTML = `
        <div class="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 text-sm mb-4">
          <p class="font-medium">No se pudo completar el pago con financieras.</p>
          <p class="mt-1">Puedes intentarlo nuevamente desde este checkout.</p>
        </div>
      `;
      params.delete('status');
      const cleanQuery = params.toString();
      window.history.replaceState({}, '', cleanQuery ? `${window.location.pathname}?${cleanQuery}` : window.location.pathname);
      return false;
    }

    if (status !== 'success') {
      return false;
    }

    container.innerHTML = `
      <div class="flex flex-col items-center justify-center py-8 text-center">
        <div class="relative">
          <div class="w-12 h-12 border-4 border-gray-200 rounded-full"></div>
          <div class="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin absolute top-0 left-0"></div>
        </div>
        <p class="text-sm text-gray-600 mt-3 font-medium">Verificando tu pago...</p>
      </div>
    `;

    this._pollSaleStatusAfterRedirect();
    return true;
  }

  _pollSaleStatusAfterRedirect() {
    if (this.checkoutStatusPoll) {
      clearInterval(this.checkoutStatusPoll);
    }

    const checkStatus = async () => {
      try {
        const response = await fetch(`/c/api/status/${this.orderUuid}/`);
        const data = await response.json();
        console.log('[WhopHandler] poll status after redirect', data);

        if (!data.success) {
          return;
        }

        if (data.status === 'PAID' || data.status === 'INSTALLMENT_PLAN_ACTIVE') {
          clearInterval(this.checkoutStatusPoll);
          window.location.href = `/c/success/${this.orderUuid}/`;
          return;
        }

        if (data.status === 'FAILED') {
          clearInterval(this.checkoutStatusPoll);
          const params = new URLSearchParams(window.location.search);
          params.set('status', 'error');
          window.location.href = `${window.location.pathname}?${params.toString()}`;
        }
      } catch (error) {
        console.error('[WHOP] Error checking checkout status:', error);
      }
    };

    checkStatus();
    this.checkoutStatusPoll = setInterval(checkStatus, 3000);
  }

  /**
   * Maneja el éxito del pago en Whop
   */
  _handleWhopSuccess(result) {
    // El webhook de Whop manejará la actualización del estado
    // Redirigir a página de éxito (orderUuid es el sale.uuid)
    const redirectUrl = `/c/success/${this.orderUuid}/`;

    // Pequeño delay para asegurar que los logs se vean
    setTimeout(() => {
      window.location.href = redirectUrl;
    }, 500);
  }

  /**
   * Maneja errores del pago en Whop
   */
  _handleWhopError(errorData) {
    console.error('[WHOP] Payment error:', errorData);

    // Extraer mensaje de error
    const errorMessage = errorData.error_message ||
                        errorData.message ||
                        errorData.error ||
                        'Error procesando el pago con Whop';

    console.error('[WHOP] Error message:', errorMessage);

    // Mostrar error al usuario
    // TODO: Integrar con el sistema de notificaciones si existe
    if (window.notificationManager) {
      window.notificationManager.showError(errorMessage);
    } else {
      alert('Error en el pago: ' + errorMessage);
    }
  }

  /**
   * Limpia recursos cuando se cambia de método de pago
   */
  destroy() {
    if (this.checkoutStatusPoll) {
      clearInterval(this.checkoutStatusPoll);
      this.checkoutStatusPoll = null;
    }

    const container = document.getElementById('whop-checkout-container');
    if (container) {
      container.innerHTML = '';
    }

    this.isInitialized = false;
    this.isLoading = false;
  }

  /**
   * Verifica si Whop está listo para procesar el pago
   */
  isReady() {
    return this.isInitialized && this.whopSessionId !== null;
  }

  /**
   * Envía el formulario de Whop programáticamente
   * Se llama desde el botón personalizado del checkout
   *
   * @returns {Promise} Promesa que se resuelve cuando el pago es exitoso o se rechaza si hay error
   */
  async submit() {
    if (!this.isReady()) {
      throw new Error('Whop checkout no está listo. Asegúrate de inicializar primero.');
    }

    if (document.body.dataset.allowSplitit === 'true') {
      if (!this.checkoutUrl) {
        throw new Error('No se pudo obtener la URL de checkout hosteada de Whop.');
      }

      console.log('[WhopHandler] redirecting to hosted checkout', {
        checkoutUrl: this.checkoutUrl,
      });
      window.location.href = this.checkoutUrl;
      return { status: 'redirecting' };
    }

    // Crear promesa para capturar el resultado del pago
    return new Promise(async (resolve, reject) => {
      // Guardar resolve/reject para el handler de éxito
      this.submitResolve = resolve;
      this.submitReject = reject;

      try {
        // Verificar que el objeto global wco esté disponible
        if (typeof window.wco === 'undefined') {
          throw new Error('El objeto wco de Whop no está disponible.');
        }

        // Llamar al método submit de Whop
        await window.wco.submit(this.embedId);

        // Esperar 2 segundos para dar tiempo a que:
        // 1. Whop valide los campos
        // 2. Whop muestre errores si los hay
        // 3. Whop procese el pago si todo está bien
        await new Promise(wait => setTimeout(wait, 2000));

        // Después de 2 segundos, si no hubo redirección significa que:
        // - Hay errores de validación que el usuario debe corregir
        // - O el pago está procesándose (el postMessage llegará después)
        // En ambos casos, quitamos el modal para que el usuario pueda ver el iframe

        // Limpiar handlers temporalmente
        this.submitResolve = null;
        this.submitReject = null;

        // Resolver la promesa para quitar el modal
        // El handler de éxito seguirá funcionando para redirigir cuando llegue el postMessage
        resolve({ status: 'pending', message: 'Waiting for payment confirmation' });

      } catch (error) {
        console.error('[WHOP] Submit error:', error);
        this.submitResolve = null;
        this.submitReject = null;
        reject(error);
      }
    });
  }

}
