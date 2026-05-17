# -*- coding: utf-8 -*-
"""SoftG XML Feed Generator — controller.

Serves the generated XML at /feed/<code>.xml.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SoftgFeedController(http.Controller):

    @http.route('/feed/<string:code>.xml', type='http', auth='public',
                csrf=False, methods=['GET'], sitemap=False)
    def serve_feed(self, code, force=None, **kw):
        """Serve a feed's cached XML, regenerating if stale or forced.

        Query parameters:
            ?force=1 — bypass cache and regenerate now (useful for testing).

        Returns:
            200 with application/xml on success
            404 if the feed doesn't exist or is inactive
            500 if generation fails
        """
        Feed = request.env['softg.feed'].sudo()
        feed = Feed.search([('code', '=', code), ('active', '=', True)], limit=1)
        if not feed:
            return request.not_found()

        # Try cache first (unless forced)
        xml_bytes = None
        if not force:
            try:
                xml_bytes = feed._get_cached_xml()
            except Exception:
                _logger.exception("Failed to read cached XML for feed %s", code)

        # No cache or stale — regenerate
        if xml_bytes is None:
            try:
                feed._generate_and_store()
                xml_bytes = feed._get_cached_xml()
                if xml_bytes is None:
                    # Cache_minutes=0 means we never cache, so re-render inline
                    xml_bytes = feed._render_feed_xml()
            except Exception as e:
                _logger.exception("Failed to generate feed %s", code)
                return request.make_response(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<error>%s</error>\n' % str(e),
                    headers=[('Content-Type', 'application/xml; charset=utf-8')],
                    status=500,
                )

        return request.make_response(
            xml_bytes,
            headers=[
                ('Content-Type', 'application/xml; charset=utf-8'),
                ('Content-Length', str(len(xml_bytes))),
                ('Cache-Control', 'public, max-age=%d' % max(feed.cache_minutes * 60, 0)),
            ],
        )
