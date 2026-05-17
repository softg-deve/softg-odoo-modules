# -*- coding: utf-8 -*-
{
    'name': 'Website News Ticker Preheader',
    'version': '19.0.1.4.0',
    'category': 'Website',
    'summary': 'Scrolling news ticker above your website header — fully manageable from the backend',
    'description': """
Website News Ticker Preheader
==============================
A smooth, always-on scrolling bar above your website header.
Managed entirely from the Odoo backend. No code. No developer.

Features
--------
- Add, edit, reorder and enable/disable messages from the backend
- Full-spectrum color picker for background, text and separator colors
- Adjustable scroll speed — type any value in seconds
- Clickable links: tel:, mailto: or any URL — icons appear automatically
- Multi-website support — assign messages per site or show on all
- Mobile responsive with auto-adjusted speed on small screens
- Auto-hides when no active messages — no blank space
- Works with any Odoo 19 theme — no theme dependency
- Default welcome messages on fresh install
    """,
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'OPL-1',
    'price': 29.99,
    'currency': 'EUR',
    'depends': ['website'],
    'images': ['static/description/banner.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/preheader_message_views.xml',
        'views/preheader_config_views.xml',
        'views/preheader_template.xml',
    ],
    'demo': ['demo/preheader_message_demo.xml'],
    'assets': {
        'web.assets_backend': [
            'website_preheader_ticker/static/src/js/hex_color_field.js',
            'website_preheader_ticker/static/src/xml/hex_color_field.xml',
        ],
        'web.assets_frontend': [
            'website_preheader_ticker/static/src/scss/preheader_ticker.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
