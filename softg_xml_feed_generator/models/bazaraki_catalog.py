# -*- coding: utf-8 -*-
"""Bazaraki taxonomy catalog: rubrics + districts.

These models hold the FULL Bazaraki taxonomy (categories + locations) as
reference data. Pre-populated on module install via post_init_hook from the
data files in data/bazaraki_*.csv. The data IS the product — users get the
full Bazaraki catalog ready to map without manual entry.

Refresh procedure: paste the latest Bazaraki guide text into the "Import
Catalog" wizard whenever Bazaraki adds new rubrics or districts.
"""
import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SoftgBazarakiRubric(models.Model):
    _name = 'softg.bazaraki.rubric'
    _description = 'Bazaraki Rubric Catalog'
    _order = 'full_path'
    _rec_name = 'display_label'

    rubric_id = fields.Char(string='Rubric ID', required=True, index=True,
                            help='Numeric Bazaraki rubric code.')
    leaf_name = fields.Char(string='Leaf Name', required=True, index=True,
                            help='The deepest segment in the taxonomy path. '
                                 'Used for fuzzy-matching against Odoo category names.')
    full_path = fields.Char(string='Full Path', required=True, index=True,
                            help='Complete taxonomy path with " / " separators.')
    display_label = fields.Char(compute='_compute_display', store=True)
    top_category = fields.Char(string='Top Category', index=True,
                               help='First segment of the path (Animals, Motors, '
                                    'Computers, etc.). Used for filtering.')

    _sql_constraints = [
        ('rubric_id_unique', 'unique(rubric_id)',
         'Bazaraki rubric ID must be unique.'),
    ]

    @api.depends('rubric_id', 'full_path')
    def _compute_display(self):
        for rec in self:
            rec.display_label = '[%s] %s' % (rec.rubric_id or '?',
                                              rec.full_path or '')


class SoftgBazarakiDistrict(models.Model):
    _name = 'softg.bazaraki.district'
    _description = 'Bazaraki District Catalog'
    _order = 'region, name'
    _rec_name = 'display_label'

    district_id = fields.Char(string='District ID', required=True, index=True,
                              help='Numeric Bazaraki district code.')
    name = fields.Char(string='District Name', required=True, index=True)
    region = fields.Char(string='Region', index=True,
                         help='Parent region: Nicosia, Limassol, Larnaca, '
                              'Paphos, or Famagusta.')
    display_label = fields.Char(compute='_compute_display', store=True)

    _sql_constraints = [
        ('district_id_unique', 'unique(district_id)',
         'Bazaraki district ID must be unique.'),
    ]

    @api.depends('district_id', 'region', 'name')
    def _compute_display(self):
        for rec in self:
            parts = []
            if rec.region:
                parts.append(rec.region)
            if rec.name:
                parts.append(rec.name)
            rec.display_label = '[%s] %s' % (rec.district_id or '?',
                                              ' / '.join(parts))
