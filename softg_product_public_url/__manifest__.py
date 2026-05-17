# -*- coding: utf-8 -*-
{
    'name': 'Product Public URL & Clean Slug',
    'version': '19.0.1.0.2',
    'category': 'Website',
    'summary': 'SEO-friendly product URLs with automatic 301 redirects on rename — never break a link again',
    'description': """
Product Public URL & Clean Slug
================================
A native Odoo module that turns long, ID-tagged product URLs into
clean, name-based slugs — and never breaks an inbound link.

Old URLs keep working via 301 redirects, new traffic gets
SEO-friendly canonical URLs, and every product carries a
copy-paste-ready absolute URL for marketplace feeds.

The Problem
-----------
Odoo's default product URLs end with the database ID — useful for
the router, ugly for customers and search engines.

You also can't rename a product without breaking every inbound link,
search engine cache, customer bookmark, and marketplace listing.

Before: /shop/65492163-dell-latitude-5330-notebook-warranty-1960
After:  /shop/dell-latitude-5330-notebook-13-3-fhd-intel-core-i5

The Solution
------------
Both URLs resolve on day one. Existing bookmarks, search-engine
cached pages, and marketplace listings keep working via 301 redirect.

Features
--------
- Clean name-based slugs replace the default <name>-<id> pattern
- Auto 301 redirects when you rename a product — SEO juice preserved
- public_url field on every product for marketplace feeds
- Smart slug chain: slug(name) → SKU → product-<id> fallback
- Auto-truncation at word boundary (default 80 chars, configurable)
- Daily cron backfills missing slugs automatically
- Bulk regenerate from list view — 820 products in 3 seconds
- No infrastructure changes — pure Odoo module
- Multi-website aware with per-site domain support

Works with
----------
- softg_xml_feed_generator — public_url used as <item_link>
- softg_product_image_publisher — same slug algorithm, filenames stay in sync
- Any Odoo theme — overrides only the URL slug, leaves theme intact
- Any feed-generator module that needs an absolute product URL
    """,
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'OPL-1',
    'price': 65.00,
    'currency': 'EUR',
    'depends': ['product', 'website_sale'],
    'images': ['static/description/banner.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_public_url_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
