# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WebsitePreheaderConfig(models.Model):
    _name = 'website.preheader.config'
    _description = 'Website Preheader Ticker Configuration'

    name = fields.Char(default='Ticker Settings')
    bg_color = fields.Char(
        string='Background Color',
        default='#1a2b3c',
        help='Click the swatch to open the color picker',
    )
    text_color = fields.Char(
        string='Text Color',
        default='#ffffff',
        help='Click the swatch to open the color picker',
    )
    sep_color = fields.Char(
        string='Separator Color',
        default='#714b67',
        help='Click the swatch to open the color picker',
    )
    speed = fields.Integer(
        string='Scroll Speed (seconds)',
        default=60,
        help='Duration of one full scroll loop in seconds. Lower = faster. Recommended: 30 (fast) · 60 (medium) · 90 (slow).',
    )
    message_ids = fields.One2many(
        'website.preheader.message', 'config_id', string='Messages',
    )

    @api.model
    def get_config(self):
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({})
        return config

    def action_open_config(self):
        config = self.sudo().get_config()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Preheader Ticker',
            'res_model': 'website.preheader.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
            'views': [(False, 'form')],
        }
