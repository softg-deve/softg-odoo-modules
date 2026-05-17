# -*- coding: utf-8 -*-
{
    'name': 'Product Image Publisher',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Products',
    'summary': 'Export product images to a local web directory and '
               'generate public URLs (Bazaraki, Google Shopping, …). '
               'Also supports the inverse direction (fetch from URL).',
    'description': """
SoftG Product Image Publisher
=============================

Bidirectional image-URL management for product feeds.

Outbound — IMAGE → URL (primary use case)
------------------------------------------
You upload images to a product the normal way (image_1920 + extra
product.image records). Click "Generate Image URLs" (or let the daily
cron do it). The module then:

* Writes the main image to ``<disk_path>/<slug>.jpg``
* Writes each extra image to ``<disk_path>/<slug>-1.jpg``, ``-2.jpg``, …
* Stores those public URLs on the product in ``image_url`` and
  ``extra_image_url_1`` … ``extra_image_url_14``

A separate web server (nginx, Apache, etc.) serves the disk directory
at the configured URL prefix.

Inbound — URL → IMAGE (legacy / import flow)
---------------------------------------------
If you paste an external URL into one of the URL fields and save, the
module downloads the image and stores it as the product's image. Useful
for importing catalogues from supplier feeds that carry image URLs.

Self-URLs (URLs whose prefix matches ``softg.image_export.url_prefix``)
are skipped during inbound fetch to prevent round-trip loops.

Configuration
-------------
Two System Parameters control behaviour:

* ``softg.image_export.disk_path`` — directory where JPEGs are written
  (must be writable by the Odoo Linux user). Default ``/var/www/robofix-images``.
* ``softg.image_export.url_prefix`` — public URL base that maps to that
  directory. Default ``https://robofix.uk/img``.

Filenames
---------
Slug priority: ``slug(name)`` → ``slug(default_code)`` → ``product-<id>``.
Example: a product named "HP Pavilion 15 Notebook" produces
``hp-pavilion-15-notebook.jpg`` for the main image and
``hp-pavilion-15-notebook-1.jpg``, ``-2.jpg``, … for extras.

Triggers
--------
* "Generate Image URLs" button on the product form
* Bulk action on the product list (Action → Generate Image URLs)
* Daily cron — exports any product whose ``write_date`` is newer than
  its last successful export
""",
    'author': 'Soft G Co. Ltd',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'website_sale',
    ],
    'external_dependencies': {
        'python': ['requests', 'PIL'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'wizard/product_image_url_wizard_view.xml',
        'views/product_template_views.xml',
        'views/ir_actions_server.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
