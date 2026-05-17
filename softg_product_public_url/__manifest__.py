# -*- coding: utf-8 -*-
{
    'name': 'Product Public URL & Clean Slug',
    'version': '19.0.1.0.2',
    'category': 'Website/eCommerce',
    'summary': 'SEO-clean product URLs (no -id suffix), automatic 301 '
               'redirects on rename, and a feed-ready absolute public URL '
               'field on every product.',
    'description': """
SoftG Product Public URL & Clean Slug
=====================================

Three features, zero configuration. Install and your shop URLs go from
``/shop/hp-pavilion-15-notebook-42`` to ``/shop/hp-pavilion-15-notebook``,
old URLs keep working via 301 redirects, and every product carries a
copy-paste-ready absolute URL for marketplace feeds.

What you get
------------
1. **Clean URLs** — ``product.template.website_url`` overridden to use
   a name-based slug (``hp-pavilion-15-notebook``) instead of Odoo's
   default ``<name>-<id>`` format. Works everywhere Odoo emits product
   URLs: shop pages, navigation, sitemaps, "Visit" buttons, email
   templates.

2. **Public URL field** — new ``public_url`` field on every product
   holds the absolute URL (``https://yourshop.com/shop/<slug>``). Feed
   generators (Bazaraki, Google Shopping, Facebook Catalog) read this
   directly instead of doing base-URL plumbing themselves.

3. **Auto-301 redirects** — rename a product, and the module
   automatically creates a 301 ``website.rewrite`` record from the old
   URL to the new one. Inbound SEO links and bookmarks never break.

Plus
----
* Collision-safe slugs — two products with the same name get the
  second one a ``-<id>`` suffix automatically.
* Reserved-path protection — never intercepts ``/shop/cart``,
  ``/shop/checkout``, ``/shop/payment``, etc.
* Backward compatible — the legacy ``/shop/<name>-<id>`` URL still
  works (Odoo's native route is untouched). Bookmarked or indexed old
  URLs are not broken on install.
* Three triggers for slug regen — on save (automatic), per-product
  button, bulk list action, and a daily cron.
* Same slug algorithm as ``softg_product_image_publisher`` — image
  filenames and product URLs stay in sync.

Designed to be sold standalone or as part of the SoftG suite.
""",
    'author': 'SoftG Ltd',
    'website': 'https://softg.shop',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'website_sale',
    ],
    'data': [
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/product_template_views.xml',
        'views/ir_actions_server.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
