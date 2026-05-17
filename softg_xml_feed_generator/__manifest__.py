# -*- coding: utf-8 -*-
{
    'name': 'XML Feed Generator — Bazaraki, Google Shopping, Facebook Catalog',
    'version': '19.0.2.1.0',
    'category': 'eCommerce',
    'summary': 'One module. Every marketplace. Build Bazaraki, Google Shopping and Facebook feeds with live polling URLs — no code.',
    'description': """
XML Feed Generator
==================
A generic XML product feed builder for Odoo with editable field mappings,
live polling URLs, and one-click presets for major marketplaces.

Ships with the full Bazaraki Cyprus rubric catalogue baked in — every
category and district pre-loaded, fuzzy auto-match to your Odoo categories included.

Features
--------
- Live polling URL at /feed/<code>.xml — marketplaces poll directly, no uploads
- 3 presets: Bazaraki Cyprus, Google Shopping (g: namespace), Facebook Catalog
- 212 Bazaraki rubrics + 168 Cyprus districts pre-loaded
- Editable field mappings — no code, drag and drop reorder
- 4 source types: product field, static value, template, image collection
- Built-in transforms: uppercase, lowercase, strip HTML, round, ISO date
- CDATA support for HTML descriptions and special characters
- Cache + hourly cron — set and forget
- Fuzzy auto-match your Odoo categories to Bazaraki taxonomy
- Preview first 3 items before going live
- Per-product marketplace fields: condition, brand, warranty, year, model

Build a Bazaraki feed in 30 seconds:
New Feed → Load Bazaraki Preset → fill in contact info → Generate.
Your live URL: yourshop.com/feed/bazaraki.xml

Works with
----------
- Bazaraki.com (Cyprus marketplace)
- Google Shopping Merchant Center
- Facebook Catalog Manager
- Any XML-based marketplace feed
- softg_product_image_publisher (image URLs)
- softg_product_public_url (product URLs)
    """,
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'OPL-1',
    'price': 175.00,
    'currency': 'EUR',
    'depends': ['base', 'website_sale'],
    'images': ['static/description/banner.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/softg_feed_views.xml',
        'views/softg_feed_mapping_views.xml',
        'views/softg_bazaraki_views.xml',
        'data/softg_bazaraki_rubric_data.xml',
        'data/softg_bazaraki_district_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
