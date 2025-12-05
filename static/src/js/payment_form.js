/** @odoo-module **/

/**
 * Copyright © Lyra Network.
 * This file is part of Izipay plugin for Odoo. See COPYING.md for license details.
 *
 * @author    Lyra Network (https://www.lyra.com/)
 * @copyright Copyright © Lyra Network
 * @license   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)
 */

import paymentForm from '@payment/js/payment_form';

let can_process_payment = true;
let popin = false;

paymentForm.include({
    init() {
        this._super(...arguments);

        // Update form token on amount update.
        $(document).ready(function () {
            if (typeof KR === 'undefined') {
                return;
            }

            const amount_total_summary = document.querySelector('#amount_total_summary');
            if (!amount_total_summary) {
                // En algunas páginas este elemento no existe, evitamos error.
                return;
            }

            const observer = new MutationObserver(function (mutations) {
                mutations.forEach(() => {
                    const checkedRadio = document.querySelectorAll("[data-payment-method-code='micuentaweb']")[0];
                    if (checkedRadio && checkedRadio.checked) {
                        console.log('Amount total summary has changed. We may have to re-create form token.');
                        checkedRadio.click();
                    }
                });
            });

            // Configure and start observing the target element for changes in child nodes.
            const config = { characterData: true, childList: true, subtree: true };
            observer.observe(amount_total_summary, config);
        });
    },

    _micuentawebGetInlineValues() {
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(radio);
        const micuentawebInlineForm = inlineForm.querySelector('[name="o_micuentaweb_element_container"]');

        return JSON.parse(
            micuentawebInlineForm.dataset.micuentawebInlineFormValues
        );
    },

    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (typeof KR === 'undefined' || paymentMethodCode !== 'micuentaweb') {
            // Devolvemos el comportamiento estándar de Odoo para otros métodos.
            return this._super(...arguments);
        }

        const inlineValues = this._micuentawebGetInlineValues();
        if (!inlineValues || Object.keys(inlineValues).length === 0) {
            return;
        }

        // Set the flow to direct to avoid redirection to payment page on Odoo payment button click.
        this._setPaymentFlow('direct');
        this._disableButton(false);

        const deliveryCarrier = document.querySelector('#delivery_carrier');
        if (deliveryCarrier !== null) {
            localStorage.removeItem('micuentawebFormToken');
            localStorage.removeItem('micuentawebFormTokenData');
        }

        // If there is already a stored token, check if payment data has changed.
        let formToken = localStorage.getItem('micuentawebFormToken');
        const tokenData = localStorage.getItem('micuentawebFormTokenData');

        if (formToken !== null && tokenData === JSON.stringify(inlineValues)) {
            console.log('Payment details did not change on method display. Use the existing token.');

            this._micuentawebDisplayEmbeddedForm(formToken, inlineValues);
        } else {
            await fetch('/payment/micuentaweb/createFormToken', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(inlineValues),
            })
                .then((response) => response.json())
                .then((data) => {
                    // If form token was not created, fallback to redirection mode.
                    if (data.formToken === false) {
                        this._setPaymentFlow('redirect');
                        this._enableButton();

                        return;
                    } else {
                        formToken = data.formToken;
                        localStorage.setItem('micuentawebFormToken', formToken);
                        localStorage.setItem('micuentawebFormTokenData', JSON.stringify(inlineValues));
                    }

                    this._micuentawebDisplayEmbeddedForm(formToken, inlineValues);
                });
        }
    },

    _micuentawebDisplayEmbeddedForm(formToken, inlineValues) {
        const wrapper = document.getElementById('micuentaweb-embedded-wrapper');
        if (!wrapper) {
            console.error('micuentaweb-embedded-wrapper not found in DOM.');
            return;
        }

        // Opcional: limpiar contenido anterior para evitar múltiples embeds.
        wrapper.innerHTML = '';

        // Create a div for embedded form.
        const embeddedDiv = document.createElement('div');
        embeddedDiv.setAttribute('class', 'kr-smart-form');

        if (inlineValues.pop_in === '1') {
            popin = true;
            embeddedDiv.setAttribute('kr-popin', '');
        } else {
            embeddedDiv.setAttribute('kr-single-payment-button', '');
        }

        if (
            inlineValues.entry_mode === 'embedded_extended_with_logos' ||
            inlineValues.entry_mode === 'embedded_extended_without_logos'
        ) {
            embeddedDiv.setAttribute('kr-card-form-expanded', '');
            if (inlineValues.entry_mode === 'embedded_extended_without_logos') {
                embeddedDiv.setAttribute('kr-no-card-logo-header', '');
            }
        }

        wrapper.appendChild(embeddedDiv);

        if (inlineValues.compact === '1') {
            KR.setFormConfig({
                cardForm: { layout: 'compact' },
                smartForm: { layout: 'compact' },
            });
        }

        KR.setFormConfig({ formToken: formToken });
        KR.onFormReady(() => this._enableButton());
    },

    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'micuentaweb') {
            // Otros proveedores: comportamiento estándar.
            return this._super(...arguments);
        }

        if (!can_process_payment) {
            return;
        }

        let formToken = localStorage.getItem('micuentawebFormToken');
        const inlineValues = this._micuentawebGetInlineValues();
        const storedTokenData = localStorage.getItem('micuentawebFormTokenData');

        if (storedTokenData === JSON.stringify(inlineValues)) {
            console.log('Payment details did not change on payment submit. Use the existing token.');
        } else {
            await fetch('/payment/micuentaweb/createFormToken', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(processingValues),
            })
                .then((response) => response.json())
                .then(async (data) => {
                    if (!data.formToken) {
                        console.log('Error while creating form token. Fallback to redirect flow.');
                        this._setPaymentFlow('redirect');
                        this._enableButton();

                        // Fallback 1: redirigir directamente si tenemos URL.
                        if (processingValues && processingValues.redirect_url) {
                            console.log('Redirecting to:', processingValues.redirect_url);
                            window.location.href = processingValues.redirect_url;
                            return;
                        }

                        // Fallback 2: usar el flujo redirect de Odoo sólo si existe el formulario.
                        // Esperamos un momento para asegurar que el DOM esté listo.
                        await new Promise(resolve => setTimeout(resolve, 100));
                        
                        const redirectForm = document.querySelector('#o_payment_redirect_form');
                        if (redirectForm) {
                            console.log('Redirect form found, processing redirect flow...');
                            
                            // Verificar que el formulario tenga los elementos necesarios
                            try {
                                return this._processRedirectFlow(
                                    providerCode,
                                    paymentOptionId,
                                    paymentMethodCode,
                                    processingValues
                                );
                            } catch (error) {
                                console.error('Error in _processRedirectFlow:', error);
                                this._displayErrorDialog(
                                    'Payment Error',
                                    'Unable to process payment redirect. Please try again or contact support.'
                                );
                                this._enableButton();
                                return;
                            }
                        } else {
                            console.error(
                                'Redirect form not found (#o_payment_redirect_form). Cannot process redirect flow.'
                            );
                            
                            // Mostrar mensaje de error al usuario
                            this._displayErrorDialog(
                                'Payment Error',
                                'Unable to initialize payment form. Please refresh the page and try again.'
                            );
                            this._enableButton();
                            return;
                        }
                    } else if (data.formToken === 'NO_UPDATE') {
                        console.log('Payment details did not change on payment submit. Use the existing token.');
                    } else {
                        formToken = data.formToken;
                        localStorage.setItem('micuentawebFormToken', formToken);
                        localStorage.setItem('micuentawebFormTokenData', JSON.stringify(inlineValues));
                    }
                })
                .catch((error) => {
                    console.error('Error creating form token:', error);
                    this._displayErrorDialog(
                        'Payment Error',
                        'Unable to connect to payment service. Please check your connection and try again.'
                    );
                    this._enableButton();
                    return;
                });
        }

        // Solo continuar si tenemos un token válido
        if (!formToken) {
            console.error('No valid form token available');
            return;
        }

        try {
            await KR.setFormConfig({ formToken: formToken });
            this._micuentawebSubmitPayment();
        } catch (error) {
            console.error('Error setting form config:', error);
            this._displayErrorDialog(
                'Payment Error',
                'Unable to initialize payment. Please try again.'
            );
            this._enableButton();
        }
    },

    _micuentawebSubmitPayment() {
        if (popin) {
            KR.openPopin();
        } else {
            KR.openSelectedPaymentMethod();
        }

        this._enableButton();
        can_process_payment = false;
    },

    async _initiatePaymentFlow(providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode === 'micuentaweb' && !can_process_payment) {
            this._micuentawebSubmitPayment();
            return;
        }

        await this._super(...arguments);
    },

    /**
     * Helper method to display error messages to the user
     */
    _displayErrorDialog(title, message) {
        if (this.call && this.call('notification', 'add')) {
            // Odoo 16+ notification system
            this.call('notification', 'add', {
                title: title,
                message: message,
                type: 'danger',
                sticky: false,
            });
        } else {
            // Fallback: usar alert si no hay sistema de notificaciones
            alert(`${title}\n\n${message}`);
        }
    },
});