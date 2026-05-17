# -*- coding: utf-8 -*-
"""Wizard: paste up to 14 extra-image URLs at once for a product.

Writes the URLs to the product's extra_image_url_N fields; the
ProductTemplate.write override fires the inbound fetch.
"""
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..models.product_template import URL_SLOTS

_logger = logging.getLogger(__name__)


class ProductImageUrlWizard(models.TransientModel):
    _name = 'product.image.url.wizard'
    _description = 'Add Extra Product Images from URLs'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        required=True,
        readonly=True,
    )
    url_1 = fields.Char(string='Extra URL 1')
    url_2 = fields.Char(string='Extra URL 2')
    url_3 = fields.Char(string='Extra URL 3')
    url_4 = fields.Char(string='Extra URL 4')
    url_5 = fields.Char(string='Extra URL 5')
    url_6 = fields.Char(string='Extra URL 6')
    url_7 = fields.Char(string='Extra URL 7')
    url_8 = fields.Char(string='Extra URL 8')
    url_9 = fields.Char(string='Extra URL 9')
    url_10 = fields.Char(string='Extra URL 10')
    url_11 = fields.Char(string='Extra URL 11')
    url_12 = fields.Char(string='Extra URL 12')
    url_13 = fields.Char(string='Extra URL 13')
    url_14 = fields.Char(string='Extra URL 14')

    def action_fetch_all(self):
        self.ensure_one()
        product = self.product_tmpl_id
        if not product:
            raise UserError(_("Wizard has no product attached."))

        url_map = {}
        for slot in URL_SLOTS:
            val = getattr(self, 'url_%d' % slot, None)
            if val and val.strip():
                url_map[slot] = val.strip()
        if not url_map:
            raise UserError(_("Please enter at least one image URL."))

        # Write all URLs in a single call; ProductTemplate.write fires fetch
        write_vals = {
            'extra_image_url_%d' % slot: url for slot, url in url_map.items()
        }
        product.write(write_vals)

        errors = []
        for slot in url_map:
            img = self.env['product.image'].search([
                ('product_tmpl_id', '=', product.id),
                ('url_slot', '=', slot),
            ], limit=1)
            if img and img.url_sync_state == 'error':
                errors.append('Slot %d: %s' % (slot, img.url_sync_error or ''))

        if errors:
            raise UserError(_(
                "%d image(s) requested, %d failed:\n\n%s"
            ) % (len(url_map), len(errors), '\n'.join(errors)))

        return {'type': 'ir.actions.act_window_close'}
