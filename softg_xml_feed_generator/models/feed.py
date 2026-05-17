# -*- coding: utf-8 -*-
"""SoftG XML Feed Generator — feed model.

Each softg.feed record is one named XML feed (Bazaraki, Google Shopping, etc.).
The feed has a list of softg.feed.mapping children that describe how to project
each product onto an XML element.
"""
import logging
import re
from datetime import datetime, timedelta
from xml.sax.saxutils import escape as xml_escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# How many products to render in the Preview button output
PREVIEW_PRODUCT_COUNT = 3

# Hard ceiling — prevents accidental infinite feeds.
MAX_PRODUCTS_PER_FEED = 50000

# Valid XML tag name pattern (simplified — letters, digits, _, -, must start
# with letter or _). Used to validate user-supplied tag names.
TAG_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_\-]*$')

# Valid feed code pattern — used in URLs, so kept ASCII-safe.
CODE_RE = re.compile(r'^[a-z0-9][a-z0-9\-_]*$')


class SoftgFeed(models.Model):
    _name = 'softg.feed'
    _description = 'SoftG XML Feed'
    _order = 'sequence, id'

    # ── Identity ────────────────────────────────────────────────────
    name = fields.Char(string='Feed Name', required=True,
                       help='Display name (e.g. "Bazaraki Cyprus").')
    code = fields.Char(string='URL Code', required=True, copy=False,
                       help='ASCII-only identifier used in the public URL. '
                            'Example: "bazaraki" → /feed/bazaraki.xml')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description',
                              help='Internal notes about this feed.')

    # ── XML structure ───────────────────────────────────────────────
    xml_declaration = fields.Char(
        string='XML Declaration', default='<?xml version="1.0" encoding="UTF-8"?>',
        help='First line of the XML output. Leave blank to omit.')
    root_tag = fields.Char(string='Root Element', default='ads', required=True,
                           help='The top-level XML tag wrapping the entire feed.')
    root_attributes = fields.Char(
        string='Root Attributes',
        help='Optional attributes for the root tag, e.g. xmlns:g="http://base.google.com/ns/1.0"')
    item_tag = fields.Char(string='Item Element', default='ad', required=True,
                           help='The XML tag wrapping each product. Bazaraki uses "ad", '
                                'Google Shopping uses "item", RSS uses "item", Atom uses "entry".')

    # ── Product scope ───────────────────────────────────────────────
    product_filter_domain = fields.Char(
        string='Product Filter',
        default="[('is_published', '=', True), ('sale_ok', '=', True)]",
        help='Odoo domain to filter products. Defaults to all published, saleable products.')
    product_limit = fields.Integer(
        string='Max Products', default=0,
        help='Maximum number of products to include. 0 = no limit (up to engine ceiling of %d).' % MAX_PRODUCTS_PER_FEED)

    # ── Mappings ────────────────────────────────────────────────────
    mapping_ids = fields.One2many(
        'softg.feed.mapping', 'feed_id', string='Field Mappings',
        copy=True)
    mapping_count = fields.Integer(string='Mappings', compute='_compute_mapping_count')

    # ── Caching / serving ───────────────────────────────────────────
    cache_minutes = fields.Integer(
        string='Cache Minutes', default=60,
        help='How long to serve cached XML before regenerating on next request. '
             '0 = always regenerate (slow under load, fresh data).')
    last_generated = fields.Datetime(string='Last Generated', readonly=True)
    last_product_count = fields.Integer(string='Last Product Count', readonly=True)
    last_size_bytes = fields.Integer(string='Last Size (bytes)', readonly=True)
    last_error = fields.Text(string='Last Error', readonly=True)

    # ── Computed URLs ───────────────────────────────────────────────
    live_url = fields.Char(string='Live URL', compute='_compute_live_url')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Feed code must be unique.'),
    ]

    # ── Constraints ─────────────────────────────────────────────────
    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ''):
                raise ValidationError(_(
                    'Feed code "%s" is invalid. Use only lowercase letters, '
                    'digits, hyphens, and underscores. Must start with a letter '
                    'or digit.') % (rec.code or '',))

    @api.constrains('root_tag', 'item_tag')
    def _check_tag_names(self):
        for rec in self:
            for label, val in (('Root Element', rec.root_tag),
                               ('Item Element', rec.item_tag)):
                if val and not TAG_NAME_RE.match(val):
                    raise ValidationError(_(
                        '%s "%s" is not a valid XML tag name.') % (label, val))

    @api.constrains('product_filter_domain')
    def _check_filter_domain(self):
        for rec in self:
            if not rec.product_filter_domain:
                continue
            try:
                domain = safe_eval(rec.product_filter_domain)
                if not isinstance(domain, list):
                    raise ValidationError(_('Product Filter must be a domain list.'))
                # Try to apply it (dry run with limit=1)
                self.env['product.template'].search(domain, limit=1)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(_(
                    'Product Filter is invalid: %s') % e)

    # ── Compute ─────────────────────────────────────────────────────
    @api.depends('mapping_ids')
    def _compute_mapping_count(self):
        for rec in self:
            rec.mapping_count = len(rec.mapping_ids)

    @api.depends('code')
    def _compute_live_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '') or ''
        base = base.rstrip('/')
        for rec in self:
            rec.live_url = '%s/feed/%s.xml' % (base, rec.code) if rec.code else ''

    # ── Actions ─────────────────────────────────────────────────────
    def action_generate(self):
        """Regenerate the feed and store it as an ir.attachment."""
        for rec in self:
            rec._generate_and_store()
        if len(self) == 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Feed Generated'),
                    'message': _('%d products written to %s in %d bytes.') % (
                        self.last_product_count, self.live_url, self.last_size_bytes),
                    'type': 'success',
                },
            }

    def action_preview(self):
        """Generate a small preview (first N products) and return the XML
        as a wizard-like notification. Useful for sanity-checking the mapping
        without committing to a full regen."""
        self.ensure_one()
        xml_bytes = self._render_feed_xml(preview_limit=PREVIEW_PRODUCT_COUNT)
        xml_text = xml_bytes.decode('utf-8', errors='replace')
        # Show in a wizard
        wizard = self.env['softg.feed.preview'].create({
            'feed_id': self.id,
            'xml_content': xml_text,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Feed Preview: %s') % self.name,
            'res_model': 'softg.feed.preview',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_live_url(self):
        self.ensure_one()
        if not self.live_url:
            raise UserError(_('Feed has no URL configured.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.live_url,
            'target': 'new',
        }

    def action_load_preset(self):
        """Open the preset selector wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load Preset'),
            'res_model': 'softg.feed.preset.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_feed_id': self.id},
        }

    # ── XML rendering ───────────────────────────────────────────────
    def _get_products(self, preview_limit=None):
        """Return products in scope for this feed, respecting filter and limits."""
        self.ensure_one()
        try:
            domain = safe_eval(self.product_filter_domain or '[]')
        except Exception:
            domain = []

        limit = preview_limit
        if limit is None:
            limit = self.product_limit if self.product_limit > 0 else MAX_PRODUCTS_PER_FEED
        else:
            limit = min(limit, MAX_PRODUCTS_PER_FEED)

        return self.env['product.template'].search(domain, limit=limit)

    def _render_feed_xml(self, preview_limit=None):
        """Generate the full XML for this feed and return bytes."""
        self.ensure_one()
        if not self.mapping_ids:
            raise UserError(_(
                'Feed "%s" has no field mappings. Add at least one mapping or '
                'load a preset before generating.') % self.name)

        products = self._get_products(preview_limit=preview_limit)
        mappings = self.mapping_ids.sorted('sequence')

        chunks = []
        if self.xml_declaration:
            chunks.append(self.xml_declaration.strip() + '\n')

        root_open = '<%s%s>' % (
            self.root_tag,
            ' ' + self.root_attributes if self.root_attributes else '',
        )
        chunks.append(root_open + '\n')

        for product in products:
            chunks.append('  <%s>\n' % self.item_tag)
            for mapping in mappings:
                rendered = mapping._render_for_product(product)
                if rendered:
                    chunks.append('    ' + rendered + '\n')
            chunks.append('  </%s>\n' % self.item_tag)

        chunks.append('</%s>\n' % self.root_tag)
        return ''.join(chunks).encode('utf-8')

    def _generate_and_store(self):
        """Render XML and store as ir.attachment for the controller to serve."""
        self.ensure_one()
        try:
            xml_bytes = self._render_feed_xml()
        except Exception as e:
            self.write({'last_error': str(e), 'last_generated': fields.Datetime.now()})
            _logger.exception("Feed generation failed for %s", self.code)
            raise UserError(_('Feed generation failed: %s') % e)

        attachment_name = self._get_attachment_name()
        existing = self.env['ir.attachment'].sudo().search(
            [('name', '=', attachment_name), ('res_model', '=', self._name),
             ('res_id', '=', self.id)], limit=1)

        vals = {
            'name': attachment_name,
            'datas': self._b64_encode(xml_bytes),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
            'type': 'binary',
        }
        if existing:
            existing.sudo().write(vals)
        else:
            self.env['ir.attachment'].sudo().create(vals)

        product_count = xml_bytes.decode('utf-8', errors='ignore').count(
            '<%s>' % self.item_tag)
        self.write({
            'last_generated': fields.Datetime.now(),
            'last_product_count': product_count,
            'last_size_bytes': len(xml_bytes),
            'last_error': False,
        })
        _logger.info("Generated feed %s: %d products, %d bytes",
                     self.code, product_count, len(xml_bytes))

    def _get_attachment_name(self):
        return 'softg_feed_%s.xml' % self.code

    @staticmethod
    def _b64_encode(data):
        import base64
        return base64.b64encode(data)

    def _get_cached_xml(self):
        """Return cached XML bytes if fresh, else None."""
        self.ensure_one()
        if self.cache_minutes <= 0:
            return None
        attachment = self.env['ir.attachment'].sudo().search(
            [('name', '=', self._get_attachment_name()),
             ('res_model', '=', self._name), ('res_id', '=', self.id)], limit=1)
        if not attachment or not attachment.datas:
            return None
        # Stale check
        age = datetime.utcnow() - attachment.write_date
        if age > timedelta(minutes=self.cache_minutes):
            return None
        import base64
        return base64.b64decode(attachment.datas)

    # ── Cron ────────────────────────────────────────────────────────
    @api.model
    def _cron_regenerate_feeds(self):
        """Daily cron — regenerate every active feed."""
        feeds = self.search([('active', '=', True)])
        _logger.info("Regenerating %d active feed(s)", len(feeds))
        for feed in feeds:
            try:
                feed._generate_and_store()
            except Exception:
                _logger.exception("Cron regen failed for feed %s", feed.code)


class SoftgFeedPreview(models.TransientModel):
    """Wizard that shows the rendered XML for the first few products."""
    _name = 'softg.feed.preview'
    _description = 'Feed Preview'

    feed_id = fields.Many2one('softg.feed', string='Feed', required=True)
    xml_content = fields.Text(string='Preview XML', readonly=True)


# ──────────────────────────────────────────────────────────────────────────
# Preset wizard — lets users one-click load a pre-built mapping set into
# a feed record.
# ──────────────────────────────────────────────────────────────────────────
class SoftgFeedPresetWizard(models.TransientModel):
    _name = 'softg.feed.preset.wizard'
    _description = 'Feed Preset Loader'

    feed_id = fields.Many2one('softg.feed', string='Feed', required=True)
    preset = fields.Selection([
        ('bazaraki', 'Bazaraki Cyprus'),
        ('google_shopping', 'Google Shopping'),
        ('facebook_catalog', 'Facebook Catalog'),
    ], string='Preset', required=True, default='bazaraki')
    replace_existing = fields.Boolean(
        string='Replace Existing Mappings', default=True,
        help='If checked, removes all current mappings on the feed before loading. '
             'If unchecked, appends to existing mappings.')

    def action_load(self):
        self.ensure_one()
        loader = getattr(self, '_load_preset_' + self.preset, None)
        if not loader:
            raise UserError(_('Unknown preset: %s') % self.preset)
        if self.replace_existing:
            self.feed_id.mapping_ids.unlink()
        loader()
        return {'type': 'ir.actions.act_window_close'}

    def _create_mappings(self, mappings_data):
        """Create mapping records from a list of dicts."""
        Mapping = self.env['softg.feed.mapping']
        seq = 10
        for data in mappings_data:
            vals = dict(data)
            vals.setdefault('feed_id', self.feed_id.id)
            vals.setdefault('sequence', seq)
            Mapping.create(vals)
            seq += 10

    def _load_preset_bazaraki(self):
        """Bazaraki Cyprus marketplace feed mappings.

        Reference: https://www.bazaraki.com/business-xml-guide/

        This preset uses the per-product and per-category fields added by this
        module. Before activating the feed, populate:

          • product.category.bazaraki_rubric_id — the Bazaraki rubric code
            for each Odoo product category (see SoftG Feeds → Bazaraki Rubric
            Mapping for a bulk-editor list view)
          • product.template.feed_condition — set per-product
            (defaults to 'new' for all products)
          • product.template.feed_brand — set per-product (optional;
            falls back to category name if empty)
          • <district> static mapping — set to your shop's Bazaraki district
            code (e.g., 5701 for Nicosia - Lykabittos, 5688 for Limassol -
            Kapsalos). Full list in the Bazaraki XML guide.
          • <contact_phone>, <contact_email> — your shop's contact info
        """
        self.feed_id.write({
            'name': self.feed_id.name or 'Bazaraki Cyprus',
            'description': 'Bazaraki Cyprus marketplace feed. Before going live: '
                           '(1) set bazaraki_rubric_id on every product category, '
                           '(2) set feed_condition per product (default "new"), '
                           '(3) fill in the <district>, <contact_phone>, '
                           '<contact_email> static mappings below.',
            'xml_declaration': '<?xml version="1.0" encoding="UTF-8"?>',
            'root_tag': 'ads',
            'item_tag': 'ad',
            'root_attributes': '',
            'product_filter_domain':
                "[('is_published', '=', True), ('sale_ok', '=', True), "
                "('list_price', '>', 0)]",
            'cache_minutes': 60,
            'product_limit': 0,
        })
        self._create_mappings([
            # ── Identification ───────────────────────────────────────
            {'xml_tag': 'id',
             'source_type': 'field', 'field_path': 'id'},

            # <title> — product name. Bazaraki strips stop-words like "for sale",
            # "selling", "cheap" etc. — they're not allowed in titles.
            {'xml_tag': 'title',
             'source_type': 'field', 'field_path': 'name'},

            # <description> — HTML stripped to plain text and CDATA-wrapped.
            {'xml_tag': 'description',
             'source_type': 'field', 'field_path': 'description_sale',
             'wrap_cdata': True, 'transform': 'strip_html'},

            # ── Pricing ──────────────────────────────────────────────
            {'xml_tag': 'price',
             'source_type': 'field', 'field_path': 'list_price',
             'transform': 'round_2'},
            {'xml_tag': 'currency',
             'source_type': 'static', 'static_value': 'EUR'},

            # ── Linking ──────────────────────────────────────────────
            {'xml_tag': 'item_link',
             'source_type': 'field', 'field_path': 'public_url',
             'wrap_cdata': True},

            # ── Images ───────────────────────────────────────────────
            {'xml_tag': 'images',
             'source_type': 'image_collection'},

            # ── Categorisation — per-category rubric ─────────────────
            # Reads from product.category.bazaraki_rubric_id, which you maintain
            # in the Bazaraki Rubric Mapping screen. omit_if_empty=False means
            # products in unmapped categories will produce <rubric/> empty tags,
            # which Bazaraki will reject — making the gap visible.
            {'xml_tag': 'rubric',
             'source_type': 'field', 'field_path': 'categ_id.bazaraki_rubric_id',
             'omit_if_empty': False},

            # ── Location ─────────────────────────────────────────────
            # Set this static value to your shop's Bazaraki district code.
            # Cyprus districts (sample):
            #   Nicosia city centre:   5701 (Lykabittos), 5700 (Agios Andreas)
            #   Limassol city:         5688 (Kapsalos), 5687 (Historical Center)
            #   Larnaca city:          5733 (Finikoudes), 5735 (Kamares)
            #   Paphos city:           5713 (Kato Paphos), 5714 (Moutallos)
            #   Famagusta area:        5729 (Paralimni), 5721 (Agia Napa)
            # Full list at https://www.bazaraki.com/business-xml-guide/
            {'xml_tag': 'district',
             'source_type': 'static', 'static_value': '',
             'omit_if_empty': False},

            # ── Per-product condition ────────────────────────────────
            {'xml_tag': 'condition',
             'source_type': 'field', 'field_path': 'feed_condition'},

            # ── Brand / model ────────────────────────────────────────
            # <make> reads feed_brand; falls back nowhere — set per product,
            # or bulk-set via Products list view.
            {'xml_tag': 'make',
             'source_type': 'field', 'field_path': 'feed_brand'},

            # <model> uses the product name as default. Override per product
            # via feed_model_override if needed (e.g., clean model code).
            {'xml_tag': 'model',
             'source_type': 'field', 'field_path': 'name'},

            # ── Warranty / delivery ──────────────────────────────────
            {'xml_tag': 'warranty',
             'source_type': 'field', 'field_path': 'feed_warranty_months'},

            # <delivery> — currently static. To make per-product, change to:
            #   source_type='field', field_path='feed_delivery_available'
            # but Bazaraki expects "yes"/"no" literals not "True"/"False", so
            # the field would need a transform (which we'd add in v2).
            {'xml_tag': 'delivery',
             'source_type': 'static', 'static_value': 'yes'},

            # ── Contact info ─────────────────────────────────────────
            # Set these static values to your shop's customer-facing contacts.
            {'xml_tag': 'contact_phone',
             'source_type': 'static', 'static_value': '',
             'omit_if_empty': False},
            {'xml_tag': 'contact_email',
             'source_type': 'static', 'static_value': '',
             'omit_if_empty': False},
        ])

    def _load_preset_google_shopping(self):
        """Google Shopping XML feed mappings (simplified)."""
        self.feed_id.write({
            'root_tag': 'rss',
            'item_tag': 'item',
            'root_attributes': 'version="2.0" xmlns:g="http://base.google.com/ns/1.0"',
            'product_filter_domain': "[('is_published', '=', True), ('sale_ok', '=', True)]",
        })
        self._create_mappings([
            {'xml_tag': 'g:id',           'source_type': 'field', 'field_path': 'id'},
            {'xml_tag': 'g:title',        'source_type': 'field', 'field_path': 'name'},
            {'xml_tag': 'g:description',  'source_type': 'field', 'field_path': 'description_sale',
             'wrap_cdata': True, 'transform': 'strip_html'},
            {'xml_tag': 'g:link',         'source_type': 'field', 'field_path': 'public_url'},
            {'xml_tag': 'g:image_link',   'source_type': 'field', 'field_path': 'image_url'},
            {'xml_tag': 'g:price',        'source_type': 'template',
             'template': '{list_price} EUR', 'transform': 'none'},
            {'xml_tag': 'g:availability', 'source_type': 'static', 'static_value': 'in stock'},
            {'xml_tag': 'g:condition',    'source_type': 'static', 'static_value': 'new'},
            {'xml_tag': 'g:brand',        'source_type': 'static', 'static_value': ''},
            {'xml_tag': 'g:gtin',         'source_type': 'field', 'field_path': 'barcode'},
            {'xml_tag': 'g:product_type', 'source_type': 'field', 'field_path': 'categ_id.name'},
        ])

    def _load_preset_facebook_catalog(self):
        """Facebook Catalog feed mappings."""
        self.feed_id.write({
            'root_tag': 'rss',
            'item_tag': 'item',
            'root_attributes': 'version="2.0" xmlns:g="http://base.google.com/ns/1.0"',
            'product_filter_domain': "[('is_published', '=', True), ('sale_ok', '=', True)]",
        })
        self._create_mappings([
            {'xml_tag': 'g:id',                'source_type': 'field', 'field_path': 'id'},
            {'xml_tag': 'g:title',             'source_type': 'field', 'field_path': 'name'},
            {'xml_tag': 'g:description',       'source_type': 'field', 'field_path': 'description_sale',
             'wrap_cdata': True, 'transform': 'strip_html'},
            {'xml_tag': 'g:link',              'source_type': 'field', 'field_path': 'public_url'},
            {'xml_tag': 'g:image_link',        'source_type': 'field', 'field_path': 'image_url'},
            {'xml_tag': 'g:availability',      'source_type': 'static', 'static_value': 'in stock'},
            {'xml_tag': 'g:condition',         'source_type': 'static', 'static_value': 'new'},
            {'xml_tag': 'g:price',             'source_type': 'template',
             'template': '{list_price} EUR'},
            {'xml_tag': 'g:brand',             'source_type': 'static', 'static_value': ''},
            {'xml_tag': 'g:google_product_category', 'source_type': 'field',
             'field_path': 'categ_id.name'},
        ])
