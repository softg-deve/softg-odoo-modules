# -*- coding: utf-8 -*-
"""SoftG Product Image Publisher — product.template extension.

Implements two directions:

OUTBOUND (primary)
    image_1920 (and extra product.image records) → JPEG files on disk →
    URL fields populated with public URLs.

INBOUND (carried from prior URL→image module)
    URL typed into a field → fetch the image, validate, re-encode, store
    as image_1920 or product.image record.
"""
import base64
import io
import logging
import os
import re
import socket
import unicodedata
from datetime import timedelta
from urllib.parse import urlparse

import requests
from PIL import Image

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
# Inbound fetch settings
FETCH_TIMEOUT = 8                       # seconds
MAX_IMAGE_SIZE = 5 * 1024 * 1024        # 5 MB
USER_AGENT = 'Odoo/19.0 SoftG-ImagePublisher/1.0'

ALLOWED_CONTENT_TYPES = (
    'image/jpeg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/tiff',
    'application/octet-stream',
)
IMAGE_MAGIC = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG': 'image/png',
    b'GIF8': 'image/gif',
    b'RIFF': 'image/webp',
    b'BM': 'image/bmp',
    b'II*\x00': 'image/tiff',
    b'MM\x00*': 'image/tiff',
}
# SSRF guard — refuse fetches against private/loopback ranges
BLOCKED_IP_PREFIXES = (
    '127.', '10.', '0.', '169.254.',
    '192.168.',
    '172.16.', '172.17.', '172.18.', '172.19.',
    '172.20.', '172.21.', '172.22.', '172.23.',
    '172.24.', '172.25.', '172.26.', '172.27.',
    '172.28.', '172.29.', '172.30.', '172.31.',
)

# Outbound export settings
JPEG_QUALITY = 90
MAX_EXTRAS = 14                         # extra_image_url_1 … _14

URL_SLOTS = list(range(1, MAX_EXTRAS + 1))   # [1, 2, …, 14]

# Refuse writing to these directories
SYSTEM_DIRS = (
    '/etc', '/root', '/boot', '/sys', '/proc', '/dev',
    '/usr', '/bin', '/sbin', '/lib', '/lib64',
)


# ======================================================================
# Helpers
# ======================================================================
def _is_private_host(host):
    try:
        ip = socket.gethostbyname(host)
        return any(ip.startswith(p) for p in BLOCKED_IP_PREFIXES)
    except socket.gaierror:
        return False


def _sniff_magic_bytes(data):
    for magic, ct in IMAGE_MAGIC.items():
        if data[:len(magic)] == magic:
            if ct == 'image/webp' and data[8:12] != b'WEBP':
                continue
            return ct
    return None


def _slugify(value):
    """Lowercase, ASCII, alphanumeric + hyphens only, no leading/trailing
    hyphens, no runs of hyphens. Returns empty string if nothing usable."""
    if not value:
        return ''
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value


def _fetch_image_from_url(url):
    """Fetch external URL, return base64-encoded re-encoded image bytes.
    Raises UserError on any validation or fetch failure."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise UserError(
            _("URL must start with http:// or https://\nGot: %s") % url)
    if parsed.hostname and _is_private_host(parsed.hostname):
        raise UserError(
            _("URL points to an internal network address:\n%s") % url)

    try:
        response = requests.get(
            url, timeout=FETCH_TIMEOUT, stream=True,
            headers={'User-Agent': USER_AGENT},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise UserError(
            _("Timed out fetching URL (limit: %ss):\n%s")
            % (FETCH_TIMEOUT, url))
    except requests.exceptions.RequestException as e:
        raise UserError(
            _("Failed to fetch URL:\n%s\n\nError: %s") % (url, str(e)))

    content_type = response.headers.get('Content-Type', '').split(';')[0]
    content_type = content_type.strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UserError(
            _("URL does not return a supported image "
              "(Content-Type: %s):\n%s") % (content_type, url))

    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_IMAGE_SIZE:
            raise UserError(
                _("Image exceeds 5 MB limit:\n%s") % url)
        chunks.append(chunk)
    raw = b''.join(chunks)
    if not raw:
        raise UserError(_("Empty response from URL:\n%s") % url)

    if content_type == 'application/octet-stream':
        sniffed = _sniff_magic_bytes(raw)
        if not sniffed:
            raise UserError(_(
                "URL returned octet-stream but the bytes are not a "
                "recognised image:\n%s") % url)
        content_type = sniffed

    try:
        pil_img = Image.open(io.BytesIO(raw))
        pil_img.verify()
        pil_img = Image.open(io.BytesIO(raw))
        output = io.BytesIO()
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            pil_img = pil_img.convert('RGBA')
            pil_img.save(output, format='PNG')
        else:
            pil_img = pil_img.convert('RGB')
            pil_img.save(output, format='JPEG', quality=JPEG_QUALITY)
        return base64.b64encode(output.getvalue())
    except Exception as e:
        raise UserError(
            _("Image could not be processed: %s\nURL: %s") % (str(e), url))


# ======================================================================
# Model
# ======================================================================
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    image_url = fields.Char(
        string='Main Image URL',
        copy=False,
        index=True,
        help="Public URL of the main product image. Auto-generated by "
             "'Generate Image URLs'. Editable for manual override "
             "(typing an external URL fetches it).",
    )
    image_url_last_export = fields.Datetime(
        string='Image URLs Last Generated',
        copy=False,
        readonly=True,
        help="Timestamp of the last successful 'Generate Image URLs' run.",
    )
    extra_image_url_1 = fields.Char(string='Extra Image URL 1', copy=False)
    extra_image_url_2 = fields.Char(string='Extra Image URL 2', copy=False)
    extra_image_url_3 = fields.Char(string='Extra Image URL 3', copy=False)
    extra_image_url_4 = fields.Char(string='Extra Image URL 4', copy=False)
    extra_image_url_5 = fields.Char(string='Extra Image URL 5', copy=False)
    extra_image_url_6 = fields.Char(string='Extra Image URL 6', copy=False)
    extra_image_url_7 = fields.Char(string='Extra Image URL 7', copy=False)
    extra_image_url_8 = fields.Char(string='Extra Image URL 8', copy=False)
    extra_image_url_9 = fields.Char(string='Extra Image URL 9', copy=False)
    extra_image_url_10 = fields.Char(string='Extra Image URL 10', copy=False)
    extra_image_url_11 = fields.Char(string='Extra Image URL 11', copy=False)
    extra_image_url_12 = fields.Char(string='Extra Image URL 12', copy=False)
    extra_image_url_13 = fields.Char(string='Extra Image URL 13', copy=False)
    extra_image_url_14 = fields.Char(string='Extra Image URL 14', copy=False)

    # ==================================================================
    # OUTBOUND DIRECTION — image_1920 → JPEG → URL
    # ==================================================================
    def _get_export_config(self):
        """Read disk_path + url_prefix from System Parameters. Validate
        that disk_path is safe and writable."""
        ICP = self.env['ir.config_parameter'].sudo()
        disk_path = (ICP.get_param(
            'softg.image_export.disk_path',
            '/var/www/robofix-images') or '').rstrip('/')
        url_prefix = (ICP.get_param(
            'softg.image_export.url_prefix',
            'https://robofix.uk/img') or '').rstrip('/')

        if not disk_path:
            raise UserError(_(
                "System Parameter 'softg.image_export.disk_path' is empty. "
                "Set it in Settings → Technical → Parameters → System Parameters."))
        if not url_prefix:
            raise UserError(_(
                "System Parameter 'softg.image_export.url_prefix' is empty. "
                "Set it in Settings → Technical → Parameters → System Parameters."))

        # Safety: refuse writing inside system dirs
        for bad in SYSTEM_DIRS:
            if disk_path == bad or disk_path.startswith(bad + '/'):
                raise UserError(_(
                    "Refusing to export images to system directory:\n%s\n\n"
                    "Choose a safe location like /var/www/robofix-images."
                ) % disk_path)

        if not os.path.isdir(disk_path):
            raise UserError(_(
                "Image export directory does not exist:\n%s\n\n"
                "Create it and ensure it's owned by the Odoo Linux user."
            ) % disk_path)
        if not os.access(disk_path, os.W_OK):
            raise UserError(_(
                "Image export directory is not writable by the Odoo user:\n%s"
            ) % disk_path)

        return disk_path, url_prefix

    def _compute_image_slug(self):
        """Slug priority: slug(name) → slug(default_code) → 'product-<id>'.
        Per Option B chosen in module design."""
        self.ensure_one()
        if self.name:
            s = _slugify(self.name)
            if s:
                return s
        if self.default_code:
            s = _slugify(self.default_code)
            if s:
                return s
        return 'product-%d' % self.id

    @staticmethod
    def _export_image_to_disk(image_b64, filepath):
        """Decode base64 image, re-encode as JPEG, write to disk atomically."""
        raw = base64.b64decode(image_b64)
        pil_img = Image.open(io.BytesIO(raw))
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        tmp = filepath + '.tmp'
        pil_img.save(tmp, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        os.replace(tmp, filepath)
        os.chmod(filepath, 0o644)

    def action_generate_image_urls(self):
        """Export main image + extras to disk, populate URL fields.

        For products in self: write image_1920 to <disk>/<slug>.jpg,
        each product.image record to <disk>/<slug>-N.jpg, and set the
        URL fields to the corresponding public URLs."""
        disk_path, url_prefix = self._get_export_config()

        successes, skips, errors = 0, 0, []

        for product in self:
            slug = product._compute_image_slug()
            vals = {}

            # ── Main image ─────────────────────────────────────────
            if product.image_1920:
                fname = '%s.jpg' % slug
                fpath = os.path.join(disk_path, fname)
                try:
                    self._export_image_to_disk(product.image_1920, fpath)
                    vals['image_url'] = '%s/%s' % (url_prefix, fname)
                    successes += 1
                except Exception as e:
                    errors.append(
                        'Product %s main image: %s' % (product.id, e))
                    _logger.exception(
                        "Failed to export main image for %s", product.id)
            else:
                vals['image_url'] = False
                skips += 1

            # ── Extras ─────────────────────────────────────────────
            extras = product.product_template_image_ids.sorted(
                key=lambda r: (r.sequence, r.id))
            for idx, img in enumerate(extras[:MAX_EXTRAS], start=1):
                slot_field = 'extra_image_url_%d' % idx
                if img.image_1920:
                    fname = '%s-%d.jpg' % (slug, idx)
                    fpath = os.path.join(disk_path, fname)
                    try:
                        self._export_image_to_disk(img.image_1920, fpath)
                        vals[slot_field] = '%s/%s' % (url_prefix, fname)
                        successes += 1
                    except Exception as e:
                        errors.append('Product %s extra %d: %s'
                                      % (product.id, idx, e))
                        _logger.exception(
                            "Failed to export extra %d for %s", idx, product.id)
                else:
                    vals[slot_field] = False

            # Clear unused slots beyond the number of extra images
            used = min(len(extras), MAX_EXTRAS)
            for slot in range(used + 1, MAX_EXTRAS + 1):
                vals['extra_image_url_%d' % slot] = False

            vals['image_url_last_export'] = fields.Datetime.now()

            # skip_url_fetch — we're writing OUR generated URLs; don't
            # trigger the inbound fetch override (would round-trip).
            product.with_context(skip_url_fetch=True).write(vals)

        msg_lines = [_('Exported %d image(s) across %d product(s).')
                     % (successes, len(self))]
        if skips:
            msg_lines.append(_('Skipped %d (no main image).') % skips)
        if errors:
            msg_lines.append(_('\n%d error(s):\n%s')
                             % (len(errors), '\n'.join(errors[:5])))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Image URL Generation'),
                'message': '\n'.join(msg_lines),
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            },
        }

    @api.model
    def _cron_export_updated_images(self):
        """Daily cron: export products whose images may have changed.

        Triggers on: never-exported, OR write_date > last_export.
        write_date as proxy for "image_1920 might have changed" — coarse
        but correct (we re-export when other fields change too).
        """
        candidates = self.search([('active', '=', True)])
        to_export = candidates.filtered(
            lambda p: not p.image_url_last_export
                      or (p.write_date and p.write_date > p.image_url_last_export)
        )
        _logger.info(
            "SoftG image publisher cron: %d/%d products need export",
            len(to_export), len(candidates))

        batch_size = 50
        done = 0
        for i in range(0, len(to_export), batch_size):
            batch = to_export[i:i + batch_size]
            for product in batch:
                try:
                    product.action_generate_image_urls()
                    done += 1
                except Exception:
                    _logger.exception(
                        "Cron export failed for product %s", product.id)
            # Commit per batch so a single failure doesn't lose all progress
            self.env.cr.commit()  # noqa: E8104 -- cron context, safe

        _logger.info(
            "SoftG image publisher cron: exported %d products", done)

    # ==================================================================
    # INBOUND DIRECTION — URL → image (legacy / import flow)
    # ==================================================================
    def _url_slot_fieldname(self, slot):
        return 'extra_image_url_%d' % slot

    def _is_self_url(self, url):
        """Skip fetch if URL matches our own image export prefix."""
        if not url:
            return False
        ICP = self.env['ir.config_parameter'].sudo()
        prefix = (ICP.get_param('softg.image_export.url_prefix') or '').rstrip('/')
        if not prefix:
            return False
        return url.strip().startswith(prefix)

    def _get_or_create_slot_image(self, slot):
        """Return the product.image record for this slot, creating if needed."""
        self.ensure_one()
        img = self.env['product.image'].search([
            ('product_tmpl_id', '=', self.id),
            ('url_slot', '=', slot),
        ], limit=1)
        if not img:
            img = self.env['product.image'].with_context(
                skip_url_fetch=True).create({
                    'product_tmpl_id': self.id,
                    'name': 'Extra Image %d' % slot,
                    'url_slot': slot,
                    'sequence': slot * 10,
                })
        return img

    def _sync_main_image_url(self, url):
        """Fetch main image URL and write to image_1920."""
        self.ensure_one()
        if not url or not url.strip() or self._is_self_url(url):
            return
        try:
            image_b64 = _fetch_image_from_url(url.strip())
            self.with_context(skip_url_fetch=True).write({
                'image_1920': image_b64,
            })
        except UserError as e:
            _logger.warning(
                "Image fetch failed for product %s main url=%s: %s",
                self.id, url, e.args[0] if e.args else e)
            raise

    def _sync_url_slot(self, slot, url):
        """Fetch a slot URL and store in the slot's product.image record."""
        self.ensure_one()
        img = self._get_or_create_slot_image(slot)
        if not url or not url.strip():
            img.with_context(skip_url_fetch=True).write({
                'image_1920': False,
                'source_url': False,
                'url_sync_state': 'pending',
                'url_sync_error': False,
            })
            return
        if self._is_self_url(url):
            # Our own URL — record it, don't fetch
            img.with_context(skip_url_fetch=True).write({
                'source_url': url.strip(),
                'url_sync_state': 'synced',
                'url_sync_error': False,
            })
            return
        try:
            image_b64 = _fetch_image_from_url(url.strip())
            filename = urlparse(url).path.split('/')[-1] \
                or ('Extra Image %d' % slot)
            img.with_context(skip_url_fetch=True).write({
                'image_1920': image_b64,
                'source_url': url.strip(),
                'name': filename,
                'url_sync_state': 'synced',
                'url_sync_error': False,
            })
        except UserError as e:
            msg = str(e.args[0]) if e.args else _('Unknown error')
            img.with_context(skip_url_fetch=True).write({
                'url_sync_state': 'error',
                'url_sync_error': msg,
            })
            raise

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get('skip_url_fetch'):
            return result

        slot_fields = {self._url_slot_fieldname(s): s for s in URL_SLOTS}
        changed_slots = {slot_fields[f]: vals[f]
                         for f in vals if f in slot_fields}
        main_changed = 'image_url' in vals

        for record in self:
            if main_changed:
                try:
                    record._sync_main_image_url(vals.get('image_url'))
                except UserError:
                    pass
            for slot, url in changed_slots.items():
                try:
                    record._sync_url_slot(slot, url)
                except UserError:
                    pass
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('skip_url_fetch'):
            return records

        slot_fields = {self._url_slot_fieldname(s): s for s in URL_SLOTS}
        for record, vals in zip(records, vals_list):
            main_url = vals.get('image_url')
            if main_url and main_url.strip():
                try:
                    record._sync_main_image_url(main_url)
                except UserError:
                    pass
            for field, slot in slot_fields.items():
                url = vals.get(field)
                if url and url.strip():
                    try:
                        record._sync_url_slot(slot, url)
                    except UserError:
                        pass
        return records

    # ------------------------------------------------------------------
    # Re-fetch button — for the inbound direction
    # ------------------------------------------------------------------
    def action_sync_all_url_images(self):
        """Re-fetch every URL on this product (skips self-URLs)."""
        self.ensure_one()
        success, errors = 0, []

        if self.image_url and self.image_url.strip() \
                and not self._is_self_url(self.image_url):
            try:
                self._sync_main_image_url(self.image_url)
                success += 1
            except UserError as e:
                errors.append('Main: %s' % (
                    str(e.args[0]) if e.args else 'error'))

        for slot in URL_SLOTS:
            url = getattr(self, self._url_slot_fieldname(slot), None)
            if url and url.strip() and not self._is_self_url(url):
                try:
                    self._sync_url_slot(slot, url)
                    success += 1
                except UserError as e:
                    errors.append('Slot %d: %s' % (
                        slot, str(e.args[0]) if e.args else 'error'))

        msg = _('%d image(s) re-fetched.') % success
        if errors:
            msg += '\n\n' + '\n'.join(errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('URL Image Re-fetch'),
                'message': msg,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            },
        }

    # ------------------------------------------------------------------
    # Bulk wrappers for list view server actions
    # ------------------------------------------------------------------
    def action_generate_image_urls_bulk(self):
        """Run action_generate_image_urls across selected products,
        swallowing per-record errors so one bad record doesn't kill batch."""
        return self.action_generate_image_urls()

    def action_sync_all_url_images_bulk(self):
        """Run re-fetch across selected products."""
        total, success = len(self), 0
        for product in self:
            try:
                product.action_sync_all_url_images()
                success += 1
            except Exception:
                _logger.exception(
                    "Bulk re-fetch failed for product %s", product.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('URL Image Re-fetch'),
                'message': _('Processed %d of %d product(s).')
                           % (success, total),
                'type': 'success',
            },
        }
