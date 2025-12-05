# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of Izipay plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

from odoo.tools.translate import _lt

# WARN: Do not modify code format here. This is managed by build files.
MICUENTAWEB_PLUGIN_FEATURES = {
    'multi': False,
    'restrictmulti': False,
    'qualif': False,
    'shatwo': True,
}

MICUENTAWEB_PARAMS = {
    'GATEWAY_CODE': 'Mi_Cuenta_Web',
    'GATEWAY_NAME': 'Izipay',
    'BACKOFFICE_NAME': 'Izipay',
    'SUPPORT_EMAIL': 'soporte@micuentaweb.pe',
    'GATEWAY_URL': 'https://secure.micuentaweb.pe/vads-payment/',
    'SITE_ID': '12345678',
    'KEY_TEST': '1111111111111111',
    'KEY_PROD': '2222222222222222',
    'CTX_MODE': 'TEST',
    'SIGN_ALGO': 'SHA-256',
    'LANGUAGE': 'es',

    'GATEWAY_VERSION': 'V2',
    'PLUGIN_VERSION': '4.2.1',
    'CMS_IDENTIFIER': 'Odoo_17-18',
    'REST_URL': 'https://api.micuentaweb.pe/api-payment/',
    'STATIC_URL': 'https://static.micuentaweb.pe/static/'
}

MICUENTAWEB_LANGUAGES = {
    'cn': _lt("Chinese"),
    'de': _lt("German"),
    'es': _lt("Spanish"),
    'en': _lt("English"),
    'fr': _lt("French"),
    'it': _lt("Italian"),
    'jp': _lt("Japanese"),
    'nl': _lt("Dutch"),
    'pl': _lt("Polish"),
    'pt': _lt("Portuguese"),
    'ru': _lt("Russian"),
    'sv': _lt("Swedish"),
    'tr': _lt("Turkish"),
}

MICUENTAWEB_CARDS = {
    'MAESTRO': u'Maestro',
    'MASTERCARD': u'Mastercard',
    'VISA': u'Visa',
    'VISA_ELECTRON': u'Visa Electron',
    'VPAY': u'V PAY',
    'AMEX': u'American Express',
    'CENCOSUD': u'Cencosud',
    'DINERS': u'Diners',
    'MASTERCARD_DEBIT': u'Mastercard Débito',
    'OH': u'OH !',
    'PAGOEFECTIVO': u'PagoEfectivo',
    'RIPLEY': u'Ripley',
    'VISA_DEBIT': u'Visa Débito',
}

MICUENTAWEB_CURRENCIES = [
    ['PEN', '604', 2],
    ['USD', '840', 2],
]

MICUENTAWEB_ONLINE_DOC_URI = {
    'es': 'https://secure.micuentaweb.pe/doc/es-PE/plugins/',
}

MICUENTAWEB_DOCUMENTATION = {
    'fr': 'Français',
    'en': 'English',
    'es': 'Español',
    'de': 'Deutsch',
    'pt': 'Português',
}

MICUENTAWEB_PAYMENT_DATA_ENTRY_MODE = {
    'redirect': _lt("Bank data acquisition on payment gateway"),
    'embedded': _lt("Embedded payment fields on merchant site (REST API)"),
    'embedded_extended_with_logos': _lt("Embedded payment fields extended on merchant site with logos (REST API)"),
    'embedded_extended_without_logos': _lt("Embedded payment fields extended on merchant site without logos (REST API)"),
}

MICUENTAWEB_REST_API_KEYS_DESC = 'REST API keys are available in your Izipay Back Office (menu: Settings > Shops > REST API keys).'