# -*- coding: utf-8 -*-
{
    'name': 'Website News Ticker Preheader',
    'version': '19.0.1.4.0',
    'category': 'Website',
    'summary': 'Scrolling news ticker above your website header — fully manageable from the backend',
    'author': 'SoftG',
    'website': 'https://www.softg.dev',
    'depends': ['website'],
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
    'license': 'LGPL-3',
}
