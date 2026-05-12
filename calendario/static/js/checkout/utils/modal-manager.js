/**
 * Gestor de modales reutilizable con animaciones
 * Responsabilidad única: Gestionar show/hide de modales con animaciones consistentes
 */
export class ModalManager {
    constructor(modalId, options = {}) {
        this.modal = document.getElementById(modalId);
        this.overlay = this.modal;
        this.content = this.modal?.querySelector('.modal-content');
        this.options = {
            closeOnOutside: true,
            closeOnEscape: true,
            ...options
        };

        this.callbacks = {
            onHide: null
        };

        this._bindEvents();
    }

    show() {
        if (!this.modal) return;

        this.modal.classList.remove('hidden');

        // Preparar animación
        this.overlay.classList.add('modal-fade-enter');
        this.content?.classList.add('modal-scale-enter');

        // Forzar reflow
        this.modal.offsetHeight;

        // Ejecutar animación
        requestAnimationFrame(() => {
            this.overlay.classList.add('modal-fade-enter-active');
            this.content?.classList.add('modal-scale-enter-active');
        });

        // Focus al primer input si existe
        setTimeout(() => {
            const firstInput = this.modal.querySelector('input, button');
            if (firstInput) firstInput.focus();
        }, 350);
    }

    hide() {
        if (!this.modal) return;

        // Iniciar animación de salida
        this._startExitAnimation();

        // Ocultar después de la animación
        setTimeout(() => {
            this.modal.classList.add('hidden');
            this._cleanupAnimation();

            // Ejecutar callback onHide si existe
            if (this.callbacks.onHide) {
                this.callbacks.onHide();
            }
        }, 250);
    }

    _startExitAnimation() {
        this.overlay.classList.remove('modal-fade-enter', 'modal-fade-enter-active');
        this.content?.classList.remove('modal-scale-enter', 'modal-scale-enter-active');

        this.overlay.classList.add('modal-fade-exit');
        this.content?.classList.add('modal-scale-exit');

        requestAnimationFrame(() => {
            this.overlay.classList.add('modal-fade-exit-active');
            this.content?.classList.add('modal-scale-exit-active');
        });
    }

    _cleanupAnimation() {
        // Remove all animation classes (both enter and exit)
        this.overlay.classList.remove(
            'modal-fade-enter',
            'modal-fade-enter-active',
            'modal-fade-exit',
            'modal-fade-exit-active'
        );
        this.content?.classList.remove(
            'modal-scale-enter',
            'modal-scale-enter-active',
            'modal-scale-exit',
            'modal-scale-exit-active'
        );
    }

    _bindEvents() {
        if (!this.modal) return;

        // Cerrar al hacer click fuera
        if (this.options.closeOnOutside) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.hide();
                }
            });
        }

        // Cerrar con escape
        if (this.options.closeOnEscape) {
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && !this.modal.classList.contains('hidden')) {
                    this.hide();
                }
            });
        }

        // Botones de cerrar automáticos
        const closeButtons = this.modal.querySelectorAll('[data-modal-close]');
        closeButtons.forEach(button => {
            button.addEventListener('click', () => this.hide());
        });
    }

    // Métodos de utilidad para pasos múltiples
    showStep(stepId) {
        // Buscar por ID de paso (para compatibilidad con HTML existente)
        const stepElement = document.getElementById(`step-${stepId}`);

        if (!stepElement) {
            console.error('Step element not found:', `step-${stepId}`);
            return;
        }

        // Ocultar todos los pasos
        const allSteps = this.modal.querySelectorAll('[id^="step-"]');
        allSteps.forEach(step => step.classList.add('hidden'));

        // Mostrar el paso solicitado
        stepElement.classList.remove('hidden');
    }

    hideStep(stepId) {
        const stepElement = document.getElementById(`step-${stepId}`);
        if (stepElement) stepElement.classList.add('hidden');
    }

    // Método para establecer callback onHide
    onHide(callback) {
        this.callbacks.onHide = callback;
    }
}