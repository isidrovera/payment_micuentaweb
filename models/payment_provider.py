# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of Izipay plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

import base64
from datetime import datetime
from hashlib import sha1, sha256
import hmac
import logging
from os import path

from pkg_resources import parse_version

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from odoo.tools import convert_xml_import
from odoo.tools import float_round
from odoo.tools import get_lang
from odoo.tools.float_utils import float_compare
from odoo.http import request

from ..controllers.main import MicuentawebController
from ..helpers import constants, tools
from .card import MicuentawebCard
from .language import MicuentawebLanguage
from odoo.addons.payment import utils as payment_utils

import urllib.parse as urlparse
import re
import json

_logger = logging.getLogger(__name__)

class ProviderMicuentaweb(models.Model):
    _inherit = 'payment.provider'

    def _get_notify_url(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        return urlparse.urljoin(base_url, MicuentawebController._notify_url)

    def _get_languages(self):
        languages = constants.MICUENTAWEB_LANGUAGES
        return [(c, l) for c, l in languages.items()]

    def _micuentaweb_compute_multi_warning(self):
        for provider in self:
            provider.micuentaweb_multi_warning = (constants.MICUENTAWEB_PLUGIN_FEATURES.get('restrictmulti') == True) if (provider.code == 'micuentawebmulti') else False

    def micuentaweb_get_doc_field_value():
        docs_uri = constants.MICUENTAWEB_ONLINE_DOC_URI
        doc_field_html = ''
        for lang, doc_uri in docs_uri.items():
            html = '<a href="%s%s">%s</a> '%(doc_uri,'odoo17/sitemap.html', constants.MICUENTAWEB_DOCUMENTATION.get(lang))
            doc_field_html += html

        return doc_field_html

    def _get_entry_modes(self):
        modes = constants.MICUENTAWEB_PAYMENT_DATA_ENTRY_MODE
        return [(c, l) for c, l in modes.items()]

    def _get_default_entry_mode(self):
        module_upgrade = self.env['ir.module.module'].search([('state', '=', 'to upgrade'), ('name', '=', 'payment_micuentaweb')])
        if module_upgrade:
            return ("redirect")

        return ("embedded")

    sign_algo_help = 'Algorithm used to compute the payment form signature. Selected algorithm must be the same as one configured in the Izipay Back Office.'

    if constants.MICUENTAWEB_PLUGIN_FEATURES.get('shatwo') == False:
        sign_algo_help += 'The HMAC-SHA-256 algorithm should not be activated if it is not yet available in the Izipay Back Office, the feature will be available soon.'

    providers = [('micuentaweb', 'Izipay - Standard payment')]
    ondelete_policy = {'micuentaweb': 'set default'}

    if constants.MICUENTAWEB_PLUGIN_FEATURES.get('multi') == True:
        providers.append(('micuentawebmulti', 'Izipay - Payment in installments'))
        ondelete_policy['micuentawebmulti'] = 'set default'

    code = fields.Selection(selection_add=providers, ondelete = ondelete_policy)

    micuentaweb_doc = fields.Html(string='Click to view the module configuration documentation', default=micuentaweb_get_doc_field_value(), readonly=True)
    micuentaweb_site_id = fields.Char(string='Shop ID', help='The identifier provided by Izipay.', default=constants.MICUENTAWEB_PARAMS.get('SITE_ID'))
    micuentaweb_key_test = fields.Char(string='Key in test mode', help='Key provided by Izipay for test mode (available in Izipay Back Office).', default=constants.MICUENTAWEB_PARAMS.get('KEY_TEST'), readonly=constants.MICUENTAWEB_PLUGIN_FEATURES.get('qualif'))
    micuentaweb_key_prod = fields.Char(string='Key in production mode', help='Key provided by Izipay (available in Izipay Back Office after enabling production mode).', default=constants.MICUENTAWEB_PARAMS.get('KEY_PROD'))
    micuentaweb_sign_algo = fields.Selection(string='Signature algorithm', help=sign_algo_help, selection=[('SHA-1', 'SHA-1'), ('SHA-256', 'HMAC-SHA-256')], default=constants.MICUENTAWEB_PARAMS.get('SIGN_ALGO'))
    micuentaweb_notify_url = fields.Char(string='Instant Payment Notification URL', help='URL to copy into your Izipay Back Office > Settings > Notification rules.', default=_get_notify_url, readonly=True)
    micuentaweb_language = fields.Selection(string='Default language', help='Default language on the payment page.', default=constants.MICUENTAWEB_PARAMS.get('LANGUAGE'), selection=_get_languages)
    micuentaweb_available_languages = fields.Many2many('micuentaweb.language', string='Available languages', column1='code', column2='label', help='Languages available on the payment page. If you do not select any, all the supported languages will be available.')
    micuentaweb_capture_delay = fields.Char(string='Capture delay', help='The number of days before the bank capture (adjustable in your Izipay Back Office).')
    micuentaweb_validation_mode = fields.Selection(string='Validation mode', help='If manual is selected, you will have to confirm payments manually in your Izipay Back Office.', selection=[('-1', 'Izipay Back Office Configuration'), ('0', 'Automatic'), ('1', 'Manual')])
    micuentaweb_payment_cards = fields.Many2many('micuentaweb.card', string='Card types', column1='code', column2='label', help='The card type(s) that can be used for the payment. Select none to use gateway configuration.')
    micuentaweb_threeds_min_amount = fields.Char(string='Manage 3DS', help='Amount below which customer could be exempt from strong authentication. Needs subscription to «Selective 3DS1» or «Frictionless 3DS2» options. For more information, refer to the module documentation.')
    micuentaweb_redirect_enabled = fields.Selection(string='Automatic redirection', help='If enabled, the buyer is automatically redirected to your site at the end of the payment.', selection=[('0', 'Disabled'), ('1', 'Enabled')])
    micuentaweb_redirect_success_timeout = fields.Char(string='Redirection timeout on success', help='Time in seconds (0-300) before the buyer is automatically redirected to your website after a successful payment.')
    micuentaweb_redirect_success_message = fields.Char(string='Redirection message on success', help='Message displayed on the payment page prior to redirection after a successful payment.', default='Redirection to shop in a few seconds...')
    micuentaweb_redirect_error_timeout = fields.Char(string='Redirection timeout on failure', help='Time in seconds (0-300) before the buyer is automatically redirected to your website after a declined payment.')
    micuentaweb_redirect_error_message = fields.Char(string='Redirection message on failure', help='Message displayed on the payment page prior to redirection after a declined payment.', default='Redirection to shop in a few seconds...')
    micuentaweb_return_mode = fields.Selection(string='Return mode', help='Method that will be used for transmitting the payment result from the payment page to your shop.', selection=[('GET', 'GET'), ('POST', 'POST')])
    micuentaweb_multi_warning = fields.Boolean(compute='_micuentaweb_compute_multi_warning')

    micuentaweb_multi_count = fields.Char(string='Count', help='Installments number')
    micuentaweb_multi_period = fields.Char(string='Period', help='Delay (in days) between installments.')
    micuentaweb_multi_first = fields.Char(string='1st installment', help='Amount of first installment, in percentage of total amount. If empty, all installments will have the same amount.')

    micuentaweb_test_password = fields.Char(string='Test password', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_prod_password = fields.Char(string='Production password', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_public_test_key = fields.Char(string='Public test key', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_public_production_key = fields.Char(string='Public production key', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_sha256_test_key = fields.Char(string='HMAC-SHA-256 test key', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_sha256_prod_key = fields.Char(string='HMAC-SHA-256 production key', help=constants.MICUENTAWEB_REST_API_KEYS_DESC)
    micuentaweb_rest_api_notify_url = fields.Char(string='REST API Notification URL', help='URL to copy into your Izipay Back Office > Settings > Notification rules.', default=_get_notify_url, readonly=True)

    micuentaweb_payment_data_entry_mode = fields.Selection(string='Payment data entry mode', help='Select how the payment data will be entered. Attention, to use the embedded payment fields, you must ensure that you have subscribed to this option with Izipay.', selection=_get_entry_modes, default=_get_default_entry_mode)
    micuentaweb_embedded_pop_in = fields.Selection(string='Display in a pop-in', help='This option allows to display the embedded payment fields in a pop-in.', selection=[('0', 'No'), ('1', 'Yes')], default='0')
    micuentaweb_embedded_theme = fields.Selection(string='Theme', help='Select a theme to use to display the embedded payment fields.', selection=[('neon', 'Neon'), ('classic', 'Classic')], default='neon')
    micuentaweb_embedded_compact_mode = fields.Selection(string='Compact mode', help='This option allows to display the embedded payment fields in a compact mode.', selection=[('0', 'Disabled'), ('1', 'Enabled')], default='0')
    micuentaweb_embedded_payment_attempts = fields.Char(string='Payment attempts number for cards', help='Maximum number of payment by cards retries after a failed payment (between 0 and 2). If blank, the gateway default value is 2.')

    image = fields.Char()
    environment = fields.Char()

    micuentaweb_redirect = False

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist Izipay providers when the currency is not supported. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name and tools.find_currency(currency.name) is None:
            providers = providers.filtered(
                lambda p: p.code not in ['micuentaweb', 'micuentawebmulti']
            )

        return providers

    @api.model
    def multi_add(self, filename, noupdate):
        if (constants.MICUENTAWEB_PLUGIN_FEATURES.get('multi') == True):
            module_upgrade = self.env['ir.module.module'].search([('state', '=', 'to upgrade'), ('name', '=', 'payment_micuentaweb')])
            file = path.join(path.dirname(path.dirname(path.abspath(__file__)))) + filename
            mode = 'update' if module_upgrade else 'init'
            convert_xml_import(self.env, 'payment_micuentaweb', file, None, mode, noupdate)

        return None

    def _get_ctx_mode(self):
        ctx_key = self.state
        ctx_value = 'TEST' if ctx_key == 'test' else 'PRODUCTION'

        return ctx_value

    def _micuentaweb_generate_sign(self, provider, values):
        key = self.micuentaweb_key_prod if self._get_ctx_mode() == 'PRODUCTION' else self.micuentaweb_key_test

        sign = ''
        for k in sorted(values.keys()):
            if k.startswith('vads_'):
                sign += values[k] + '+'

        sign += key

        if self.micuentaweb_sign_algo == 'SHA-1':
            shasign = sha1(sign.encode('utf-8')).hexdigest()
        else:
            shasign = base64.b64encode(hmac.new(key.encode('utf-8'), sign.encode('utf-8'), sha256).digest()).decode('utf-8')

        return shasign

    def _micuentaweb_payment_config(self, amount):
        if self.code == 'micuentawebmulti':
            if (self.micuentaweb_multi_first):
                first = int(float(self.micuentaweb_multi_first) / 100 * int(amount))
            else:
                first = int(float(amount) / float(self.micuentaweb_multi_count))

            payment_config = u'MULTI:first=' + str(first) + u';count=' + self.micuentaweb_multi_count + u';period=' + self.micuentaweb_multi_period
        else:
            payment_config = u'SINGLE'

        return payment_config

    def micuentaweb_form_generate_values(self, values):
        base_url = request.httprequest.host_url

        threeds_mpi = u''
        if self.micuentaweb_threeds_min_amount and float(self.micuentaweb_threeds_min_amount) > values['amount']:
            threeds_mpi = u'2'

        # Check currency.
        if 'currency' in values:
            currency = values['currency']
        else:
            currency = self.env['res.currency'].browse(values['currency_id']).exists()

        currency_num = tools.find_currency(currency.name)
        if currency_num is None:
            _logger.error('The plugin cannot find a numeric code for the current shop currency {}.'.format(currency.name))
            raise ValidationError(_('The shop currency {} is not supported.').format(currency.name))

        # Amount in cents.
        k = int(currency.decimal_places)
        amount = int(float_round(float_round(values['amount'], k) * (10 ** k), 0))

        # List of available languages.
        available_languages = ''
        for value in self.micuentaweb_available_languages:
            available_languages += value.code + ';'

        # List of available payment cards.
        payment_cards = ''
        for value in self.micuentaweb_payment_cards:
            payment_cards += value.code + ';'

        # Validation mode.
        validation_mode = self.micuentaweb_validation_mode if self.micuentaweb_validation_mode != '-1' else ''

        # Enable redirection?
        ProviderMicuentaweb.micuentaweb_redirect = True if str(self.micuentaweb_redirect_enabled) == '1' else False

        order_id = re.sub("[^0-9a-zA-Z_-]+", "", values.get('reference'))

        tx_values = dict() # Values to sign in unicode.
        tx_values.update({
            'vads_site_id': self.micuentaweb_site_id,
            'vads_amount': str(amount),
            'vads_currency': currency_num,
            'vads_trans_date': str(datetime.utcnow().strftime("%Y%m%d%H%M%S")),
            'vads_trans_id': tools.generate_trans_id(),
            'vads_ctx_mode': str(self._get_ctx_mode()),
            'vads_page_action': u'PAYMENT',
            'vads_action_mode': u'INTERACTIVE',
            'vads_payment_config': self._micuentaweb_payment_config(amount),
            'vads_version': constants.MICUENTAWEB_PARAMS.get('GATEWAY_VERSION'),
            'vads_url_return': urlparse.urljoin(base_url, MicuentawebController._return_url),
            'vads_order_id': str(order_id),
            'vads_ext_info_order_ref': str(values.get('reference')),
            'vads_contrib': tools._micuentaweb_get_contrib(),

            'vads_language': self.micuentaweb_language or '',
            'vads_available_languages': available_languages,
            'vads_capture_delay': self.micuentaweb_capture_delay or '',
            'vads_validation_mode': validation_mode,
            'vads_payment_cards': payment_cards,
            'vads_return_mode': str(self.micuentaweb_return_mode),
            'vads_threeds_mpi': threeds_mpi
        })

        if ProviderMicuentaweb.micuentaweb_redirect:
            tx_values.update({
                'vads_redirect_success_timeout': self.micuentaweb_redirect_success_timeout or '',
                'vads_redirect_success_message': self.micuentaweb_redirect_success_message or '',
                'vads_redirect_error_timeout': self.micuentaweb_redirect_error_timeout or '',
                'vads_redirect_error_message': self.micuentaweb_redirect_error_message or ''
            })

        micuentaweb_tx_values = dict() # Values encoded in UTF-8.

        for key in tx_values.keys():
            if tx_values[key] == ' ':
                tx_values[key] = ''

            micuentaweb_tx_values[key] = tx_values[key].encode('utf-8')

        return micuentaweb_tx_values

    def micuentaweb_generate_values_from_order(self, data):
        sale_order = request.env['sale.order'].sudo().search([('id', '=', data['order_id'])]).exists()

        currency = self._micuentaweb_get_currency(data['currency_id'])
        amount = float(sale_order.amount_total)
        amount = int(float_round(float_round(amount, int(currency[1])) * (10 ** int(currency[1])), 0))

        partner_id = data['partner_id']
        partner = self.env['res.partner'].browse(partner_id)

        invoice_address = sale_order.partner_invoice_id
        partner_name = invoice_address.name or partner.name
        partner_first_name, partner_last_name = payment_utils.split_partner_name(partner_name)

        values = dict() # Values to sign in unicode.
        values.update({
            'invoice_address_id': invoice_address.id,
            'vads_amount': amount,
            'vads_order_id': sale_order.name,
            'vads_contrib': tools._micuentaweb_get_contrib(),
            'vads_language': self.micuentaweb_language or '',
            'vads_cust_id': str(partner_id) or '',
            'vads_cust_first_name': partner_first_name and partner_first_name[0:62] or '',
            'vads_cust_last_name': partner_last_name and partner_last_name[0:62] or '',
            'vads_cust_address': invoice_address.street and invoice_address.street[0:254] or '',
            'vads_cust_zip': invoice_address.zip and invoice_address.zip[0:62] or '',
            'vads_cust_city': invoice_address.city and invoice_address.city[0:62] or '',
            'vads_cust_state': invoice_address.state_id.code and invoice_address.state_id.code[0:62] or '',
            'vads_cust_country': invoice_address.country_id.code and invoice_address.country_id.code.upper() or '',
            'vads_cust_email': invoice_address.email and invoice_address.email[0:126] or '',
            'vads_cust_phone': invoice_address.phone and invoice_address.phone[0:31] or '',
        })

        try:
            shipping_address = sale_order.partner_shipping_id

            partner_shipping_first_name, partner_shipping_last_name = payment_utils.split_partner_name(shipping_address.name) or ('', '')
            partner_ship_to_street = shipping_address.street and shipping_address.street[0:62] or ''
            partner_ship_to_zip = shipping_address.zip and shipping_address.zip[0:62] or ''
            partner_ship_to_city = shipping_address.city and shipping_address.city[0:62] or ''
            partner_ship_to_state = shipping_address.state_id.name and shipping_address.state_id.name[0:62] or ''
            partner_ship_to_country = shipping_address.country_id.code and shipping_address.country_id.code.upper() or ''
            partner_ship_to_phone_num = shipping_address.phone and shipping_address.phone[0:31] or ''
            shipping_address_id = shipping_address.id

        except Exception:
            partner_shipping_first_name = values['vads_cust_first_name']
            partner_shipping_last_name = values['vads_cust_last_name']
            partner_ship_to_street = values['vads_cust_address'] and values['vads_cust_address'][0:62] or ''
            partner_ship_to_zip = values['vads_cust_zip']
            partner_ship_to_city = values['vads_cust_city']
            partner_ship_to_state = values['vads_cust_state']
            partner_ship_to_country = values['vads_cust_country']
            partner_ship_to_phone_num = values['vads_cust_phone']
            shipping_address_id = values['invoice_address_id']

        values.update({
            'shipping_address_id': shipping_address_id,
            'vads_ship_to_first_name': partner_shipping_first_name and partner_shipping_first_name[0:62] or '',
            'vads_ship_to_last_name': partner_shipping_last_name and partner_shipping_last_name[0:62] or '',
            'vads_ship_to_street': partner_ship_to_street,
            'vads_ship_to_zip': partner_ship_to_zip,
            'vads_ship_to_city': partner_ship_to_city,
            'vads_ship_to_state': partner_ship_to_state,
            'vads_ship_to_country': partner_ship_to_country,
            'vads_ship_to_phone_num': partner_ship_to_phone_num
        })

        return values

    def micuentaweb_get_form_action_url(self):
        return constants.MICUENTAWEB_PARAMS.get('GATEWAY_URL')

    def _get_default_payment_method_codes(self):
        if self.code != 'micuentaweb' and self.code != 'micuentawebmulti':
            return super()._get_default_payment_method_codes()

        return self.code

    def get_micuentaweb_currencies(self):
        first_elements = []
        for currency in constants.MICUENTAWEB_CURRENCIES:
            first_element = currency[0]
            first_elements.append(first_element)

        return first_elements

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code in ['micuentaweb', 'micuentawebmulti']:
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in self.get_micuentaweb_currencies()
            )

        return supported_currencies

    def _micuentaweb_get_rest_password(self):
        if self.state == 'test':
            return str(self.micuentaweb_test_password)

        return str(self.micuentaweb_prod_password)

    def _micuentaweb_get_rest_public_key(self):
        if self.state == 'test':
            return str(self.micuentaweb_public_test_key)

        return str(self.micuentaweb_public_production_key)

    def _micuentaweb_get_rest_sha256_key(self):
        if self.state == 'test':
            return str(self.micuentaweb_sha256_test_key)

        return str(self.micuentaweb_sha256_prod_key)

    def _micuentaweb_get_javascript_server_url(self):
        return constants.MICUENTAWEB_PARAMS.get('STATIC_URL') + "js/krypton-client/V4.0/stable/kr-payment-form.min.js"

    def _micuentaweb_get_embedded_stylesheet_url(self):
        return constants.MICUENTAWEB_PARAMS.get('STATIC_URL') + "js/krypton-client/V4.0/ext/" + self.micuentaweb_embedded_theme + "-reset.css"

    def _micuentaweb_get_embedded_stylesheet_script_url(self):
        return constants.MICUENTAWEB_PARAMS.get('STATIC_URL') + "js/krypton-client/V4.0/ext/" + self.micuentaweb_embedded_theme + ".js"

    def _micuentaweb_get_return_url(self):
        return urlparse.urljoin(self.env['ir.config_parameter'].get_param('web.base.url'), MicuentawebController._return_url)

    def _micuentaweb_get_embedded_language(self):
        return get_lang(self.env).code[:2]

    def _micuentaweb_get_embedded_payment_means(self):
        cards = []
        for value in self.micuentaweb_payment_cards:
            cards.append(value.code)

        return cards

    def _micuentaweb_get_currency(self, currency_id):
        # Give the iso and the number of decimal toward the smallest monetary unit from the id of the currency.
        currency_name = tools.find_currency(self.env['res.currency'].search([('id', '=', currency_id)]).exists().name) 
        for currency in constants.MICUENTAWEB_CURRENCIES:
            if currency[1] == str(currency_name):
                return (currency[0], currency[2])

        return None

    def _micuentaweb_get_inline_form_values(
        self, amount, currency, partner_id, is_validation, payment_method_sudo, sale_order_id, **kwargs
    ):
        sale_order = request.env['sale.order'].sudo().search([('id', '=', sale_order_id)]).exists()
        values = {
            "provider_id": self.id,
            "provider_code" : "micuentaweb",
            "order_id": str(sale_order_id),
            "amount": amount,
            "currency_id": currency.id,
            "partner_id": partner_id,
            "invoice_address_id": sale_order.partner_invoice_id.id,
            "shipping_address_id": sale_order.partner_shipping_id.id,
            "entry_mode": self.micuentaweb_payment_data_entry_mode,
            "pop_in": self.micuentaweb_embedded_pop_in,
            "compact": self.micuentaweb_embedded_compact_mode
        }

        return json.dumps(values)

    def _should_build_inline_form(self, is_validation=True):
        if (self.code == 'micuentawebmulti'):
            return False

        if (self.code == 'micuentaweb'):
            if (str(self.micuentaweb_payment_data_entry_mode) != 'redirect'):
                return True

            return False

        return super()._should_build_inline_form(is_validation=True)