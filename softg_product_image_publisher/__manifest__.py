# -*- coding: utf-8 -*-
{
    'name': 'Product Image Publisher — Public URLs for Marketplaces',
    'version': '19.0.1.0.0',
    'category': 'eCommerce',
    'summary': 'Export Odoo product images as real .jpg public URLs — ready for Google Shopping, Facebook Catalog and Bazaraki',
    'description': """
Product Image Publisher
=======================
Native Odoo module that turns your local product images into
feed-ready public URLs in one click.

Designed for marketplaces, Google Shopping, Facebook Catalog,
and any consumer that demands real .jpg endpoints instead of
Odoo's internal /web/image route.

The Problem
-----------
Marketplaces want real URLs ending in .jpg or .png.
Odoo's built-in /web/image/ route returns images without file
extensions, with internal-looking paths, and often fails
marketplace validators outright.

The Solution
------------
Product Image Publisher writes your product images directly to a
static web directory served by nginx at a real public URL.

Before: odoo.example.com/web/image/product.template/42/image_1920
After:  yourshop.com/img/hp-pavilion-15-notebook.jpg

Features
--------
- One-click publish — generate URLs for all products at once
- 15 image slots per product: 1 main + 14 extras
- SEO-friendly filenames from product name (slug)
- Daily auto-sync via cron — zero manual intervention
- Bulk operations from list view
- Import images from URLs (bidirectional)
- SSRF-protected inbound — refuses private/loopback IPs
- Config via System Parameters — no code edits
- Processed 371 images across 810 products in under 90 seconds

Works with
----------
- Bazaraki.com Cyprus marketplace
- Google Shopping Merchant Center
- Facebook Catalog Manager
- softg_xml_feed_generator (image_url field)
- Headless storefronts (Next.js, Nuxt, Astro)
- Supplier sync feeds
    """,
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'OPL-1',
    'price': 92.00,
    'currency': 'EUR',
    'depends': ['product', 'website_sale'],
    'images': ['static/description/banner.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_image_publisher_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
