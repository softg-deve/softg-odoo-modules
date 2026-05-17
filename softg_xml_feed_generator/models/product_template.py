# -*- coding: utf-8 -*-
"""Per-product marketplace feed fields.

These are GENERIC marketplace concepts (condition, brand, warranty) that
multiple feeds use — not Bazaraki-specific. The Bazaraki preset references
them via field_path, but so could a Google Shopping or Facebook preset.
"""
from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    feed_condition = fields.Selection(
        [
            ('new',          'New'),
            ('like_new',     'Like New'),
            ('refurbished',  'Refurbished'),
            ('used',         'Used'),
            ('for_parts',    'For Parts / Not Working'),
        ],
        string='Marketplace Condition',
        default='new',
        help='Used by XML feed exports (Bazaraki, Google Shopping, Facebook). '
             'Maps to <condition> in Bazaraki, <g:condition> in Google.')

    feed_brand = fields.Char(
        string='Marketplace Brand',
        help='Brand / manufacturer name for marketplace feeds. Falls back to '
             'the internal category name in the Bazaraki preset if left empty.')

    feed_warranty_months = fields.Integer(
        string='Warranty (months)',
        default=12,
        help='Warranty duration in months, shown in marketplace listings.')

    feed_model_override = fields.Char(
        string='Marketplace Model',
        help='Optional override for the <model> element in feeds. If empty, '
             'the product name is used. Set this when the product name differs '
             'from the marketplace model designation (e.g., long marketing name '
             'vs. clean model code like "Dell Latitude 5330").')

    feed_year = fields.Integer(
        string='Year',
        help='Year of manufacture or release. Used by some marketplaces as a '
             'filter criterion (cars, electronics, etc.).')

    feed_delivery_available = fields.Boolean(
        string='Delivery Available',
        default=True,
        help='Whether you ship this product. Maps to <delivery>yes/no</delivery> '
             'in Bazaraki and shipping flags in other feeds.')

    @api.model
    def _feed_delivery_yes_no(self):
        """Helper for templates: returns 'yes'/'no' based on the boolean."""
        # Not currently used — template engine doesn't call Python helpers.
        # Reserved for v2 where we may add computed source_type.
        return 'yes' if self.feed_delivery_available else 'no'
