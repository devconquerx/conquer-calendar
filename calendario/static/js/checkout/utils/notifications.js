/**
 * Sistema de notificaciones unificado para el checkout.
 * Maneja estados de loading, errores específicos por gateway y feedback visual.
 * Combina funcionalidad básica y avanzada en una sola clase.
 */

export class NotificationManager {
    constructor() {
        this.container = this._createContainer();
        this.loadingNotifications = new Map();
    }

    _createContainer() {
        let container = document.getElementById('enhanced-notifications');

        if (!container) {
            container = document.createElement('div');
            container.id = 'enhanced-notifications';
            container.className = 'fixed top-4 right-4 z-50 space-y-2 max-w-sm';
            document.body.appendChild(container);
        }

        return container;
    }

    show(message, type = 'info', options = {}) {
        const {
            duration = 5000,
            closable = true,
            persistent = false,
            id = null,
            actions = []
        } = options;

        const notification = this._createNotification(message, type, {
            closable,
            persistent,
            id,
            actions
        });

        this.container.appendChild(notification);

        // Auto-remove después del duration (a menos que sea persistente)
        if (!persistent && duration > 0) {
            setTimeout(() => {
                this._removeNotification(notification);
            }, duration);
        }

        return notification;
    }

    showLoading(message, id = 'loading') {
        const notification = this.show(message, 'loading', {
            persistent: true,
            closable: false,
            id: id
        });

        this.loadingNotifications.set(id, notification);
        return notification;
    }

    hideLoading(id = 'loading') {
        const notification = this.loadingNotifications.get(id);
        if (notification) {
            this._removeNotification(notification);
            this.loadingNotifications.delete(id);
        }
    }

    showPaymentProcessing(gatewayCode) {
        const messages = {
            'STRIPE': 'Procesando pago con tarjeta...',
            'DLOCAL': 'Preparando redirección a dLocal...',
            'BANK_TRANSFER': 'Procesando transferencia bancaria...'
        };

        const message = messages[gatewayCode] || 'Procesando pago...';
        return this.showLoading(message, 'payment-processing');
    }

    hidePaymentProcessing() {
        this.hideLoading('payment-processing');
    }

    showSuccess(message, options = {}) {
        return this.show(message, 'success', {
            duration: 3000,
            ...options
        });
    }

    showError(message, options = {}) {
        return this.show(message, 'error', {
            duration: 7000,
            ...options
        });
    }

    showWarning(message, options = {}) {
        return this.show(message, 'warning', {
            duration: 5000,
            ...options
        });
    }

    showInfo(message, options = {}) {
        return this.show(message, 'info', {
            duration: 4000,
            ...options
        });
    }

    showGatewaySpecificError(gatewayCode, errorType, message) {
        const enhancedMessage = this._enhanceErrorMessage(gatewayCode, errorType, message);
        const actions = this._getErrorActions(gatewayCode, errorType);

        return this.showError(enhancedMessage, {
            actions: actions,
            duration: 10000
        });
    }

    _enhanceErrorMessage(gatewayCode, errorType, originalMessage) {
        const enhancements = {
            'STRIPE': {
                'payment_processing': `Stripe: ${originalMessage}`,
                'card_declined': 'Tu tarjeta fue rechazada. Verifica los datos e inténtalo con otra tarjeta.',
                'insufficient_funds': 'Fondos insuficientes. Inténtalo con otra tarjeta o método de pago.'
            },
            'DLOCAL': {
                'payment_processing': `dLocal: ${originalMessage}`,
                'redirect_failed': 'No se pudo conectar con dLocal. Inténtalo de nuevo en unos segundos.'
            },
            'BANK_TRANSFER': {
                'payment_processing': `Transferencia: ${originalMessage}`
            }
        };

        return enhancements[gatewayCode]?.[errorType] || originalMessage;
    }

    _getErrorActions(gatewayCode, errorType) {
        const actions = [];

        if (gatewayCode === 'STRIPE' && (errorType === 'card_declined' || errorType === 'insufficient_funds')) {
            actions.push({
                text: 'Cambiar método de pago',
                action: () => {
                    const paymentSection = document.querySelector('.payment-methods');
                    if (paymentSection) {
                        paymentSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            });
        }

        if (errorType === 'network_error') {
            actions.push({
                text: 'Reintentar',
                action: () => {
                    if (window.checkoutApp?.modules?.paymentProcessor) {
                        window.checkoutApp.modules.paymentProcessor.processPayment();
                    }
                }
            });
        }

        return actions;
    }

    _createNotification(message, type, options = {}) {
        const { closable = true, id = null, actions = [] } = options;

        const notification = document.createElement('div');
        notification.className = `notification notification-${type} transform transition-all duration-300 ease-in-out`;

        if (id) {
            notification.dataset.notificationId = id;
        }

        // Estilos base
        const baseClasses = 'flex items-start p-4 rounded-lg shadow-lg border';
        const typeClasses = {
            'success': 'bg-green-50 border-green-200 text-green-800',
            'error': 'bg-red-50 border-red-200 text-red-800',
            'warning': 'bg-yellow-50 border-yellow-200 text-yellow-800',
            'info': 'bg-blue-50 border-blue-200 text-blue-800',
            'loading': 'bg-gray-50 border-gray-200 text-gray-800'
        };

        notification.className = `${baseClasses} ${typeClasses[type] || typeClasses.info}`;

        // Icono
        const icon = this._getIcon(type);

        // Contenido
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 ml-3';

        const messageDiv = document.createElement('div');
        messageDiv.className = 'text-sm font-medium';
        messageDiv.textContent = message;
        contentDiv.appendChild(messageDiv);

        // Acciones
        if (actions.length > 0) {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'mt-2 space-x-2';

            actions.forEach(action => {
                const button = document.createElement('button');
                button.className = 'text-xs px-2 py-1 rounded bg-white border border-current hover:bg-gray-50 transition-colors';
                button.textContent = action.text;
                button.onclick = action.action;
                actionsDiv.appendChild(button);
            });

            contentDiv.appendChild(actionsDiv);
        }

        // Botón de cerrar
        const closeButton = document.createElement('button');
        if (closable) {
            closeButton.className = 'flex-shrink-0 ml-2 text-gray-400 hover:text-gray-600 transition-colors';
            closeButton.innerHTML = '&times;';
            closeButton.onclick = () => this._removeNotification(notification);
        }

        // Ensamblar
        notification.appendChild(icon);
        notification.appendChild(contentDiv);
        if (closable) {
            notification.appendChild(closeButton);
        }

        // Animación de entrada
        notification.style.transform = 'translateX(100%)';
        notification.style.opacity = '0';

        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);

        return notification;
    }

    _getIcon(type) {
        const iconContainer = document.createElement('div');
        iconContainer.className = 'flex-shrink-0';

        const icons = {
            'success': '✓',
            'error': '✕',
            'warning': '⚠',
            'info': 'ℹ',
            'loading': '⟳'
        };

        iconContainer.textContent = icons[type] || icons.info;

        if (type === 'loading') {
            iconContainer.style.animation = 'spin 1s linear infinite';
            // Agregar CSS de spin si no existe
            if (!document.getElementById('notification-spin-styles')) {
                const style = document.createElement('style');
                style.id = 'notification-spin-styles';
                style.textContent = `
                    @keyframes spin {
                        from { transform: rotate(0deg); }
                        to { transform: rotate(360deg); }
                    }
                `;
                document.head.appendChild(style);
            }
        }

        return iconContainer;
    }

    _removeNotification(notification) {
        if (!notification || !notification.parentNode) return;

        // Animación de salida
        notification.style.transform = 'translateX(100%)';
        notification.style.opacity = '0';

        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    hideAll() {
        const notifications = this.container.querySelectorAll('.notification');
        notifications.forEach(notification => {
            this._removeNotification(notification);
        });
        this.loadingNotifications.clear();
    }

    hideById(id) {
        const notification = this.container.querySelector(`[data-notification-id="${id}"]`);
        if (notification) {
            this._removeNotification(notification);
        }
    }
}

// Alias para retrocompatibilidad
export const EnhancedNotificationManager = NotificationManager;