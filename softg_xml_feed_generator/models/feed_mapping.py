# -*- coding: utf-8 -*-
"""SoftG XML Feed Generator — mapping model.

Each softg.feed.mapping describes how to render ONE XML element for a product.
The source can be a product field path, a static string, a template string
with {placeholders}, or a special image-collection that emits multiple
<image> children for image_url + extra_image_url_1..14.
"""
import logging
import re
from xml.sax.saxutils import escape as xml_escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Pattern used in template-type mappings: {field_path}
TEMPLATE_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_\.]*)\}')

# Valid XML tag name (same as in feed.py)
TAG_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_\-]*$')

# Field names checked for the image-collection mode
IMAGE_COLLECTION_FIELDS = ['image_url'] + [
    'extra_image_url_%d' % i for i in range(1, 15)
]


class SoftgFeedMapping(models.Model):
    _name = 'softg.feed.mapping'
    _description = 'SoftG Feed Field Mapping'
    _order = 'feed_id, sequence, id'

    feed_id = fields.Many2one(
        'softg.feed', string='Feed', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    xml_tag = fields.Char(string='XML Tag', required=True,
                         help='The XML element name, e.g. "title", "price", "id".')

    source_type = fields.Selection([
        ('field', 'Product Field'),
        ('static', 'Static Value'),
        ('template', 'Template String'),
        ('image_collection', 'Image Collection'),
    ], string='Source', default='field', required=True,
       help='Where this XML element\'s value comes from.\n\n'
            '• Product Field — reads a field from the product (e.g. "name", "list_price", '
            '"categ_id.name", "image_url"). Supports dotted paths.\n'
            '• Static Value — a fixed string (e.g. "EUR", a district code, a phone number).\n'
            '• Template String — text with {placeholders} resolved against product fields '
            '(e.g. "https://shop.com/p/{product_slug}").\n'
            '• Image Collection — emits multiple <tag> children for image_url + '
            'extra_image_url_1..14, skipping empty slots. Use for Bazaraki <images> wrapper.')

    field_path = fields.Char(
        string='Field Path',
        help='Dotted path to a product field, e.g. "name", "list_price", '
             '"categ_id.name", "image_url", "seller_ids.partner_id.phone".')
    static_value = fields.Char(string='Static Value')
    template = fields.Char(
        string='Template',
        help='String with {placeholders} like "https://shop.com/p/{product_slug}".')

    wrap_cdata = fields.Boolean(
        string='Wrap in CDATA', default=False,
        help='Wrap the value in <![CDATA[...]]>. Use for HTML descriptions or '
             'any value that may contain XML-unsafe characters that you want to '
             'preserve literally.')
    omit_if_empty = fields.Boolean(
        string='Omit if Empty', default=True,
        help='If the resolved value is empty or false, skip this element entirely '
             'rather than emitting an empty tag.')

    transform = fields.Selection([
        ('none', 'None'),
        ('upper', 'Uppercase'),
        ('lower', 'Lowercase'),
        ('strip_html', 'Strip HTML tags'),
        ('round_2', 'Round to 2 decimals'),
        ('iso_date', 'Format as ISO date'),
    ], string='Transform', default='none',
       help='Optional transformation applied to the resolved value.')

    # ── Constraints ─────────────────────────────────────────────────
    @api.constrains('xml_tag')
    def _check_tag(self):
        for rec in self:
            if not TAG_NAME_RE.match(rec.xml_tag or ''):
                raise ValidationError(_(
                    'XML Tag "%s" is not a valid XML element name.') % (rec.xml_tag or ''))

    @api.constrains('source_type', 'field_path', 'static_value', 'template')
    def _check_source_filled(self):
        for rec in self:
            if rec.source_type == 'field' and not rec.field_path:
                raise ValidationError(_(
                    'Mapping "%s": Field Path is required when Source is "Product Field".'
                ) % rec.xml_tag)
            if rec.source_type == 'static' and rec.static_value is False:
                raise ValidationError(_(
                    'Mapping "%s": Static Value is required when Source is "Static Value".'
                ) % rec.xml_tag)
            if rec.source_type == 'template' and not rec.template:
                raise ValidationError(_(
                    'Mapping "%s": Template is required when Source is "Template String".'
                ) % rec.xml_tag)

    # ── Rendering ───────────────────────────────────────────────────
    def _read_field_path(self, product, path):
        """Read a dotted field path from a product, returning '' on any failure
        instead of raising. Empty links anywhere in the chain return ''."""
        if not path:
            return ''
        val = product
        for segment in path.split('.'):
            if val is False or val is None:
                return ''
            try:
                val = getattr(val, segment)
            except (AttributeError, KeyError):
                return ''
            if val is False or val is None:
                return ''
            # Recordsets: pick the first record so the chain can continue
            if hasattr(val, '_name') and hasattr(val, '__len__'):
                if len(val) == 0:
                    return ''
                if len(val) > 1:
                    # For multi-record traversal we'd need list handling;
                    # for the common case, take the first record.
                    val = val[0]
        if val is False or val is None:
            return ''
        return val

    def _apply_template(self, product, template_str):
        """Resolve {placeholders} in the template against product fields."""
        def replace(m):
            path = m.group(1)
            val = self._read_field_path(product, path)
            return self._stringify(val)
        return TEMPLATE_RE.sub(replace, template_str)

    @staticmethod
    def _stringify(val):
        """Coerce any field value into a string for XML output."""
        if val is False or val is None:
            return ''
        if isinstance(val, str):
            return val
        # Recordsets: use display name if available
        if hasattr(val, '_name'):
            if hasattr(val, 'display_name'):
                return val.display_name or ''
            return str(val) if val else ''
        if isinstance(val, bytes):
            try:
                return val.decode('utf-8', errors='replace')
            except Exception:
                return ''
        return str(val)

    def _apply_transform(self, value):
        """Apply the transform setting to a string value."""
        if not value:
            return value
        t = self.transform
        if t == 'upper':
            return value.upper()
        if t == 'lower':
            return value.lower()
        if t == 'strip_html':
            try:
                from lxml import html as lxml_html
                stripped = lxml_html.fromstring('<root>%s</root>' % value).text_content()
                return stripped.strip()
            except Exception:
                # Fallback regex strip
                return re.sub(r'<[^>]+>', '', value).strip()
        if t == 'round_2':
            try:
                return '%.2f' % float(value)
            except (ValueError, TypeError):
                return value
        if t == 'iso_date':
            try:
                from datetime import datetime, date
                if isinstance(value, (datetime, date)):
                    return value.isoformat()
                return str(value)
            except Exception:
                return value
        return value

    def _resolve_value(self, product):
        """Return the resolved STRING value for this mapping for the given
        product. May return '' to indicate empty.

        Note: for source_type='image_collection', this returns a LIST of
        strings (one per non-empty image URL) rather than a single string.
        _render_for_product handles the list case specially."""
        self.ensure_one()
        if self.source_type == 'field':
            val = self._read_field_path(product, self.field_path or '')
            return self._apply_transform(self._stringify(val))
        if self.source_type == 'static':
            return self._apply_transform(self.static_value or '')
        if self.source_type == 'template':
            return self._apply_transform(self._apply_template(product, self.template or ''))
        if self.source_type == 'image_collection':
            urls = []
            for fname in IMAGE_COLLECTION_FIELDS:
                if not hasattr(product, fname):
                    continue
                v = getattr(product, fname, '') or ''
                if v:
                    urls.append(self._stringify(v))
            return urls
        return ''

    def _render_for_product(self, product):
        """Render this mapping as a single XML fragment string (not including
        the leading indent or trailing newline — feed.py adds those).
        Returns '' if the mapping should emit nothing."""
        self.ensure_one()
        value = self._resolve_value(product)

        # Image collection: emit multiple child elements
        if self.source_type == 'image_collection':
            if not value:
                return '' if self.omit_if_empty else '<%s/>' % self.xml_tag
            inner = []
            for url in value:
                if self.wrap_cdata:
                    inner.append('<image><![CDATA[%s]]></image>' % url)
                else:
                    inner.append('<image>%s</image>' % xml_escape(url))
            return '<%s>%s</%s>' % (self.xml_tag, ''.join(inner), self.xml_tag)

        # Single value
        if not value:
            return '' if self.omit_if_empty else '<%s/>' % self.xml_tag

        if self.wrap_cdata:
            return '<%s><![CDATA[%s]]></%s>' % (self.xml_tag, value, self.xml_tag)
        return '<%s>%s</%s>' % (self.xml_tag, xml_escape(value), self.xml_tag)
