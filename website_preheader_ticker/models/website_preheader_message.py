# -*- coding: utf-8 -*-
from odoo import fields, models


class WebsitePreheaderMessage(models.Model):
    _name = 'website.preheader.message'
    _description = 'Website Preheader Ticker Message'
    _order = 'sequence, id'

    name = fields.Char(string='Message', required=True, translate=True)
    href = fields.Char(string='Link')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    website_id = fields.Many2one('website', string='Website', ondelete='cascade')
    config_id = fields.Many2one('website.preheader.config', string='Config', ondelete='set null')
