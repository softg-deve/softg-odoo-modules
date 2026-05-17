# -*- coding: utf-8 -*-
"""SoftG Product Public URL & Clean Slug.

Adds two stored fields to product.template:

* ``product_slug`` — clean, deterministic, collision-safe slug
  derived from the product name. Falls back to slugified SKU, then
  ``product-<id>``. On collision, the product ID is appended.
* ``public_url`` — absolute storefront URL. Uses the clean
  ``/shop/<slug>`` form when product_slug is set; falls back to the
  native ``/shop/<name>-<id>`` form otherwise.

Overrides Odoo's native ``website_url`` field to use the clean slug
when present (so 'Visit' buttons, breadcrumbs, sitemaps all emit clean
URLs). Auto-creates a ``website.rewrite`` 301 redirect whenever a
product's slug changes, preserving SEO for renamed products.
"""
import logging
import re
import unicodedata

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Slug helper — kept byte-compatible with softg_product_image_publisher
# so image filenames and product URLs share the same slug.
# ----------------------------------------------------------------------
def _slugify(value):
    """Lowercase ASCII, alphanumeric + hyphens, no leading/trailing
    hyphens, no runs of hyphens. Returns '' if input is unusable."""
    if not value:
        return ''
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value


def _truncate_at_word_boundary(slug, max_length):
    """Truncate slug to at most ``max_length`` characters, breaking at the
    last hyphen if doing so doesn't cut more than half the slug.

    Returns the slug unchanged when ``max_length`` is 0 (disabled) or
    the slug is already short enough."""
    if not max_length or len(slug) <= max_length:
        return slug
    truncated = slug[:max_length]
    last_hyphen = truncated.rfind('-')
    # Prefer hyphen-boundary truncation, but don't cut so aggressively
    # that we lose more than half the original window
    if last_hyphen > max_length // 2:
        truncated = truncated[:last_hyphen]
    return truncated.rstrip('-')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    product_slug = fields.Char(
        string='URL Slug',
        copy=False,
        index=True,
        help="Clean, name-based slug used as the product's website URL "
             "and as the image filename base. Auto-computed from the "
             "product name on save, falling back to slugified SKU and "
             "then to product-<id>. On collision, the product ID is "
             "appended for uniqueness.",
    )
    public_url = fields.Char(
        string='Public URL',
        compute='_compute_public_url',
        store=True,
        index=True,
        help="Absolute storefront URL. Uses the clean /shop/<slug> form "
             "when a slug is set, otherwise falls back to Odoo's native "
             "/shop/<name>-<id> form.",
    )

    # ==================================================================
    # Override website_url to use the clean slug
    # ==================================================================
    def _compute_website_url(self):
        """Override Odoo's native website_url computation. Records with
        ``product_slug`` set get ``/shop/<slug>``; others fall through
        to Odoo's default ``/shop/<name>-<id>`` behavior."""
        records_with_slug = self.filtered('product_slug')
        records_default = self - records_with_slug

        if records_default:
            super(ProductTemplate, records_default)._compute_website_url()

        for rec in records_with_slug:
            rec.website_url = '/shop/%s' % rec.product_slug

    # ==================================================================
    # Slug computation
    # ==================================================================
    def _build_slug_for_product(self):
        """Compute the slug for *this* product based on name → SKU → id,
        with collision detection against other products. Truncates the
        slug at the System Parameter limit (default 80 chars)."""
        self.ensure_one()
        base = _slugify(self.name) or _slugify(self.default_code) or ''
        if not base:
            return 'product-%d' % self.id if self.id else False

        # Truncate at System-Parameter-configured length (default 80)
        try:
            max_len = int(self.env['ir.config_parameter'].sudo().get_param(
                'softg.public_url.max_slug_length', '80'))
        except (TypeError, ValueError):
            max_len = 80
        base = _truncate_at_word_boundary(base, max_len)

        if not self.id:
            # During create, can't disambiguate yet; assign base.
            # The post-create hook will append -id if needed.
            return base

        collision = self.search([
            ('product_slug', '=', base),
            ('id', '!=', self.id),
        ], limit=1)
        if collision:
            return '%s-%d' % (base, self.id)
        return base

    def _refresh_slug(self):
        """Recompute and write the slug. Creates a 301 redirect if the
        slug changed from a previous non-empty value."""
        for rec in self:
            new_slug = rec._build_slug_for_product()
            if not new_slug or new_slug == rec.product_slug:
                continue
            old_slug = rec.product_slug
            rec.with_context(skip_slug_recompute=True).write({
                'product_slug': new_slug,
            })
            # Only create a redirect if there was a *previous* slug —
            # not on first-time assignment.
            if old_slug:
                rec._create_url_redirect(old_slug, new_slug)

    # ==================================================================
    # public_url — uses clean slug when available, falls back otherwise
    # ==================================================================
    @api.depends('product_slug', 'website_url')
    def _compute_public_url(self):
        # Resolve base URL: prefer the website's configured domain (per-website),
        # fall back to the global web.base.url ICP. This matches Odoo's own
        # behaviour for product page URLs in templates and emails.
        ICP = self.env['ir.config_parameter'].sudo()
        fallback_base = (ICP.get_param('web.base.url', '') or '').rstrip('/')

        for rec in self:
            base = fallback_base
            try:
                website = rec.website_id or self.env['website'].search(
                    [], order='id', limit=1)
                if website:
                    web_base = website.get_base_url() or website.domain
                    if web_base:
                        base = web_base.rstrip('/')
                        # website.domain may be stored without a scheme
                        if not base.startswith(('http://', 'https://')):
                            base = 'https://' + base
            except Exception:
                _logger.exception(
                    "Failed to read website base URL for product %s", rec.id)

            if rec.product_slug:
                rec.public_url = '%s/shop/%s' % (base, rec.product_slug)
            elif rec.website_url:
                path = rec.website_url
                if not path.startswith('/'):
                    path = '/' + path
                rec.public_url = '%s%s' % (base, path)
            else:
                rec.public_url = False

    # ==================================================================
    # 301 redirect creation
    # ==================================================================
    def _create_url_redirect(self, old_slug, new_slug):
        """Create or update a 301 redirect from /shop/<old> to /shop/<new>.

        Uses ``website.rewrite`` (Odoo 16+). Falls back gracefully if the
        model name differs in a future version or isn't available."""
        if not old_slug or not new_slug or old_slug == new_slug:
            return

        Model = self.env.get('website.rewrite') \
                or self.env.get('website.redirect')
        if Model is None:
            _logger.warning(
                "Neither website.rewrite nor website.redirect model found; "
                "cannot create 301 for %s -> %s", old_slug, new_slug)
            return

        old_url = '/shop/%s' % old_slug
        new_url = '/shop/%s' % new_slug

        # Avoid duplicate redirects — if one already exists for the old
        # URL, update its target instead of stacking new records.
        try:
            existing = Model.sudo().search(
                [('url_from', '=', old_url)], limit=1)
        except Exception:
            existing = Model.browse()       # defensive — search fields differ across versions

        try:
            if existing:
                existing.write({
                    'url_to': new_url,
                    'redirect_type': '301',
                })
                _logger.info(
                    "Updated 301 redirect: %s -> %s", old_url, new_url)
            else:
                Model.sudo().create({
                    'name': 'SoftG slug redirect: %s -> %s' % (old_slug, new_slug),
                    'url_from': old_url,
                    'url_to': new_url,
                    'redirect_type': '301',
                })
                _logger.info(
                    "Created 301 redirect: %s -> %s", old_url, new_url)
        except Exception:
            # Log but don't propagate — a missing redirect should not
            # prevent the product save from completing.
            _logger.exception(
                "Failed to create/update 301 for %s -> %s",
                old_slug, new_slug)

    # ==================================================================
    # write / create — keep slug in sync, trigger redirects
    # ==================================================================
    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get('skip_slug_recompute'):
            return result

        if 'name' in vals or 'default_code' in vals:
            for rec in self:
                rec._refresh_slug()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('skip_slug_recompute'):
            return records
        for rec in records:
            rec._refresh_slug()
        return records

    # ==================================================================
    # User-facing actions
    # ==================================================================
    def action_regenerate_public_url(self):
        """Recompute slug + public URL for selected products.
        public_url is store=True with @api.depends('product_slug'), so
        writing the slug automatically triggers Odoo to recompute and
        persist public_url. No manual invalidation needed."""
        success, errors = 0, []
        for rec in self:
            try:
                rec._refresh_slug()
                success += 1
            except Exception as e:
                _logger.exception(
                    "Public URL regen failed for product %s", rec.id)
                errors.append('Product %s: %s' % (rec.id, e))

        msg = _('Regenerated %d product(s).') % success
        if errors:
            msg += '\n\n' + _('%d error(s):\n') % len(errors) \
                + '\n'.join(errors[:5])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Public URL Regeneration'),
                'message': msg,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            },
        }

    @api.model
    def _cron_backfill_public_urls(self):
        """Daily cron: assign slugs to any product missing one, then
        recompute public URLs if needed."""
        to_fix = self.search([
            '|',
            ('product_slug', '=', False),
            ('public_url',   '=', False),
        ])
        _logger.info(
            "SoftG public URL cron: %d products to backfill", len(to_fix))

        batch_size = 200
        for i in range(0, len(to_fix), batch_size):
            batch = to_fix[i:i + batch_size]
            for rec in batch:
                try:
                    rec._refresh_slug()
                except Exception:
                    _logger.exception(
                        "Cron backfill failed for product %s", rec.id)
            self.env.cr.commit()  # noqa: E8104 -- cron context, safe

        _logger.info("SoftG public URL cron: done")
