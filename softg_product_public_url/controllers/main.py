# -*- coding: utf-8 -*-
"""SoftG clean-URL controller.

Adds a route ``/shop/<slug>`` that resolves a product by its
``product_slug`` field, then delegates to Odoo's standard product
page handler. Odoo's native ``/shop/<model:product>`` route is left
untouched, so old ``/shop/<name>-<id>`` URLs keep working.
"""
import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


# Reserved subpaths under /shop/ — these must NEVER be intercepted by
# our slug router. Keeping this list defensive prevents 404s if Werkzeug
# route precedence ever shifts between Odoo versions.
RESERVED_SHOP_PATHS = {
    'cart',
    'checkout',
    'confirm_order',
    'confirmation',
    'payment',
    'print',
    'address',
    'update_address',
    'extra_info',
    'pricelist',
    'change_pricelist',
    'tracking_orders',
    'page',
    'category',
    'products',
    'product',
    'shop',
    'static',
}


class SoftGCleanProductURL(WebsiteSale):
    """Clean-URL route. Matches /shop/<slug> when slug doesn't have a
    trailing ``-<id>`` (those are caught by Odoo's native route first)."""

    @http.route(
        ['/shop/<string:softg_slug>'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,        # sitemap already covered by parent route
    )
    def softg_product_by_slug(self, softg_slug, category=None, search='', **kwargs):
        # Guard against intercepting reserved /shop/* paths
        if softg_slug in RESERVED_SHOP_PATHS:
            return request.not_found()

        # Empty / pathological inputs
        if not softg_slug or '/' in softg_slug:
            return request.not_found()

        # Look up product by clean slug.
        # sudo() so unpublished/inaccessible records don't leak via ACL,
        # but is_published filter ensures only public products resolve.
        product = request.env['product.template'].sudo().search([
            ('product_slug', '=', softg_slug),
            ('is_published', '=', True),
        ], limit=1)

        if not product:
            return request.not_found()

        # Delegate to the standard product-page renderer (calls the
        # inherited @http.route method as a plain Python call).
        return self.product(
            product,
            category=category,
            search=search,
            **kwargs,
        )
