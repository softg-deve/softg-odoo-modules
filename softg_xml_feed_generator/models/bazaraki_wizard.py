# -*- coding: utf-8 -*-
"""Bazaraki catalog: paste-import wizard + auto-suggest logic.

Two user-facing actions:

1. ImportWizard — paste the raw Bazaraki guide text (from
   https://www.bazaraki.com/business-xml-guide/), wizard parses it and
   creates softg.bazaraki.rubric + softg.bazaraki.district records.
   Idempotent: re-running deletes existing records and reloads.

2. action_auto_suggest_rubric — on product.category, fuzzy-matches the
   category name against the rubric catalog and pre-fills bazaraki_rubric_id
   where confidence is high.
"""
import difflib
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Pattern matching one rubric line: "<path> <numeric_id>"
RUBRIC_LINE = re.compile(r'^(.+?)\s+(\d+)\s*$')
# Pattern matching one district line: "<numeric_id> | <name>"
DISTRICT_LINE = re.compile(r'^(\d+)\s*\|\s*(.+?)\s*$')
# Known Cyprus region names — switching to a region context
REGIONS = {'Nicosia', 'Limassol', 'Larnaca', 'Paphos', 'Famagusta'}


class SoftgBazarakiImportWizard(models.TransientModel):
    _name = 'softg.bazaraki.import.wizard'
    _description = 'Bazaraki Catalog Import'

    raw_text = fields.Text(
        string='Bazaraki Guide Text', required=True,
        help='Paste the raw text from https://www.bazaraki.com/business-xml-guide/. '
             'Both rubrics (Categories) and districts (Locations) sections will be parsed.')
    purge_existing = fields.Boolean(
        string='Replace Existing Catalog', default=True,
        help='If checked, wipes the current catalog before loading. Recommended.')
    rubric_count = fields.Integer(string='Rubrics Imported', readonly=True)
    district_count = fields.Integer(string='Districts Imported', readonly=True)
    state = fields.Selection([
        ('input', 'Input'),
        ('done', 'Done'),
    ], default='input')

    def action_import(self):
        self.ensure_one()
        Rubric = self.env['softg.bazaraki.rubric']
        District = self.env['softg.bazaraki.district']

        if self.purge_existing:
            Rubric.search([]).unlink()
            District.search([]).unlink()

        rubrics, districts = self._parse(self.raw_text or '')
        for r in rubrics:
            Rubric.create(r)
        for d in districts:
            District.create(d)

        self.write({
            'rubric_count': len(rubrics),
            'district_count': len(districts),
            'state': 'done',
        })
        _logger.info("Bazaraki catalog import: %d rubrics, %d districts",
                     len(rubrics), len(districts))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'softg.bazaraki.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @staticmethod
    def _parse(text):
        """Parse the raw Bazaraki text into (rubrics, districts).

        The page format alternates: rubric lines first (taxonomy paths with a
        trailing numeric id), then "Locations" section with region headers
        followed by district lines ("<id> | <name>")."""
        rubrics = []
        districts = []
        seen_rubrics = set()
        seen_districts = set()
        current_region = None
        in_districts_section = False

        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            # Region header switches us into districts mode for this region
            if line in REGIONS:
                current_region = line
                in_districts_section = True
                continue
            if line == 'Districts':
                continue

            # District line: "<id> | <name>"
            m_district = DISTRICT_LINE.match(line)
            if m_district and in_districts_section:
                did = m_district.group(1)
                name = m_district.group(2)
                if did not in seen_districts:
                    seen_districts.add(did)
                    districts.append({
                        'district_id': did,
                        'name': name,
                        'region': current_region or '',
                    })
                continue

            # Rubric line: "<path> <id>" — must contain " / " (taxonomy) to
            # avoid catching random numbers in headers
            m_rubric = RUBRIC_LINE.match(line)
            if m_rubric:
                path = m_rubric.group(1).strip()
                rid = m_rubric.group(2)
                # Sanity checks: rubric paths always contain at least one slash,
                # district IDs are 4-digit numbers starting with 5xxx.
                if rid in seen_rubrics:
                    continue
                if not ' / ' in path and len(path.split()) < 2:
                    # Single-word with number could be junk
                    continue
                # Top-level rubrics may lack slashes — accept if it's a known
                # top branch
                seen_rubrics.add(rid)
                leaf = path.rsplit(' / ', 1)[-1].strip() if ' / ' in path else path
                top = path.split(' / ', 1)[0].strip() if ' / ' in path else path
                rubrics.append({
                    'rubric_id': rid,
                    'leaf_name': leaf,
                    'full_path': path,
                    'top_category': top,
                })

        return rubrics, districts


class ProductCategory(models.Model):
    _inherit = 'product.category'

    def action_auto_suggest_rubric(self):
        """Fuzzy-match category name against the Bazaraki rubric catalog and
        fill in bazaraki_rubric_id where confidence is high. Safe to re-run."""
        Rubric = self.env['softg.bazaraki.rubric']
        all_rubrics = Rubric.search([])
        if not all_rubrics:
            raise UserError(_(
                'Bazaraki rubric catalog is empty. Go to '
                'SoftG Feeds → Bazaraki → Import Catalog and paste the '
                'Bazaraki guide text first.'))

        # Build a {lowercase_leaf_name: rubric_record} lookup for exact hits
        leaf_lookup = {}
        for r in all_rubrics:
            key = (r.leaf_name or '').lower().strip()
            if key:
                leaf_lookup.setdefault(key, []).append(r)

        # Also collect (leaf_name_lower, rubric) pairs for fuzzy fallback
        leaf_names = list(leaf_lookup.keys())

        matched, skipped, ambiguous = 0, 0, 0
        for cat in self:
            if cat.bazaraki_rubric_id:
                skipped += 1
                continue

            cat_name = (cat.name or '').lower().strip()
            if not cat_name:
                skipped += 1
                continue

            # Try exact match first
            exact = leaf_lookup.get(cat_name, [])
            if len(exact) == 1:
                cat.write({
                    'bazaraki_rubric_id': exact[0].rubric_id,
                    'bazaraki_rubric_name': exact[0].full_path,
                })
                matched += 1
                continue
            if len(exact) > 1:
                # Multiple rubrics share this leaf name — leave for user
                ambiguous += 1
                continue

            # Fuzzy match — accept if best ratio >= 0.85
            close = difflib.get_close_matches(cat_name, leaf_names,
                                              n=1, cutoff=0.85)
            if close:
                best_key = close[0]
                best_rubric = leaf_lookup[best_key][0]
                cat.write({
                    'bazaraki_rubric_id': best_rubric.rubric_id,
                    'bazaraki_rubric_name': best_rubric.full_path,
                })
                matched += 1
            else:
                skipped += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto-Suggest Complete'),
                'message': _(
                    'Matched: %d · Skipped: %d · Ambiguous: %d\n'
                    'Re-run the action to retry after editing category names. '
                    'Ambiguous matches need manual selection.'
                ) % (matched, skipped, ambiguous),
                'type': 'success' if matched else 'warning',
                'sticky': True,
            },
        }
