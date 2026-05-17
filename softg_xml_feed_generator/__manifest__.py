{
    'name': 'XML Feed Generator',
    'version': '19.0.2.1.0',
    'summary': 'Generic XML feed builder with editable field mappings — Bazaraki, '
               'Google Shopping, Facebook Catalog, and any custom marketplace feed. '
               'Ships with full Bazaraki rubric + district catalog and auto-match.',
    'description': """
SoftG XML Feed Generator
========================
Build any XML product feed with editable field mappings and serve it at a
live URL marketplaces can poll. Ships with one-click presets for Bazaraki,
Google Shopping, and Facebook Catalog — and the mapping editor lets you adapt
to any custom XML schema without touching code.

Features
--------
- Multiple feeds per database (one for Bazaraki, one for Google, etc.)
- Editable field mapping with source types: product field, static value,
  template string, image collection
- Live URL at /feed/<code>.xml with cached attachment + auto-regeneration
- Per-feed product filter (domain) — only published, only in stock, etc.
- Dotted field paths (categ_id.name, seller_ids.partner_id.phone)
- CDATA wrapping, transforms (upper, lower, strip_html, round_2, iso_date)
- One-click "Load Preset" for Bazaraki Cyprus / Google Shopping / Facebook
- Daily cron regenerates all active feeds automatically
- Preview button shows live XML output for first 3 products

Pairs naturally with:
- softg_product_image_publisher — populates image_url / extra_image_url_*
- softg_product_public_url — populates public_url for <item_link>
""",
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'LGPL-3',
    'category': 'Website/Website',
    'depends': [
        'base',
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/feed_presets.xml',
        'views/feed_mapping_views.xml',
        'views/feed_views.xml',
        'views/product_template_views.xml',
        'views/product_category_views.xml',
        'views/bazaraki_catalog_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
