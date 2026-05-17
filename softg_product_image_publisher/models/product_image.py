# -*- coding: utf-8 -*-
"""Extends product.image with URL-tracking metadata.

These fields are used by the inbound (URL → image) direction of the
publisher. They record which extra_image_url_N slot the image was
fetched from and the last sync state, so failed fetches are visible
without blocking the save.
"""
from odoo import fields, models


class ProductImage(models.Model):
    _inherit = 'product.image'

    source_url = fields.Char(
        string='Source URL',
        index=True,
        help="URL the image was fetched from. Updated automatically when "
             "the corresponding extra_image_url_N field on the template "
             "changes.",
    )
    url_slot = fields.Integer(
        string='URL Slot',
        default=0,
        index=True,
        help="Which extra_image_url_N field manages this image. "
             "0 = manually-added (not URL-driven).",
    )
    url_sync_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('synced', 'Synced'),
            ('error', 'Error'),
        ],
        string='Sync State',
        default='pending',
        readonly=True,
    )
    url_sync_error = fields.Char(
        string='Sync Error',
        readonly=True,
        help="Last error message from the URL fetch, if any.",
    )
