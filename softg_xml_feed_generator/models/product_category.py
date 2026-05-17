# -*- coding: utf-8 -*-
"""Per-category Bazaraki rubric mapping.

Each Odoo product category gets a free-text Char field holding the Bazaraki
rubric number (e.g., 263 for Laptops, 267 for Monitors). All products in that
category inherit it via field_path 'categ_id.bazaraki_rubric_id' in the feed
mapping.

Reference list: https://www.bazaraki.com/business-xml-guide/

Common IT shop rubrics (Computers, gaming branch):
    264  Desktops, servers
    263  Laptops, notebooks
    267  Monitors
    265  Printers, scanners
    2787 Laptop parts, tools
    3362 Desktop parts / CPU
    3364 Desktop parts / GPU
    3365 Desktop parts / Motherboards
    3367 Desktop parts / RAM
    3368 Desktop parts / SSD, HDD
    3366 Desktop parts / PSU
    3360 Desktop parts / Cases
    3361 Desktop parts / Cooling
    3370 Desktop parts / Other
    3348 PC, Laptop accessories / Cables, adaptors
    3349 PC, Laptop accessories / External hard drives
    3350 PC, Laptop accessories / Hubs
    3351 PC, Laptop accessories / Keyboards
    3354 PC, Laptop accessories / Mouses
    3355 PC, Laptop accessories / UPS
    3356 PC, Laptop accessories / USB sticks
    3357 PC, Laptop accessories / Webcams
    3358 PC, Laptop accessories / Sets
    3359 PC, Laptop accessories / Other
    3371 Routers, modems, switches / Modems
    3375 Tablets, accessories / Tablets
"""
from odoo import _, api, fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    bazaraki_rubric_id = fields.Char(
        string='Bazaraki Rubric ID',
        help='Numeric Bazaraki rubric code (e.g., 263 for Laptops, 267 for '
             'Monitors). Look up the correct rubric for each category at '
             'https://www.bazaraki.com/business-xml-guide/')
    bazaraki_rubric_name = fields.Char(
        string='Bazaraki Rubric Name',
        help='Optional descriptive name for reference, e.g. '
             '"Computers, gaming / Laptops, notebooks". Not used in the feed; '
             'just helps you remember what rubric ID 263 actually represents.')
