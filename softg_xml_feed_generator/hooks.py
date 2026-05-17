# -*- coding: utf-8 -*-
"""Module-level hooks.

post_init_hook runs once when the module is installed (NOT on upgrade).
It reads data/bazaraki_default_catalog.txt and ingests it via the same
parser used by the user-facing import wizard, so the database arrives with
the Bazaraki taxonomy pre-loaded.
"""
import logging
import os

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Load the bundled Bazaraki rubric + district catalog."""
    catalog_path = os.path.join(
        os.path.dirname(__file__), 'data', 'bazaraki_default_catalog.txt')
    if not os.path.exists(catalog_path):
        _logger.warning(
            "Bazaraki default catalog file not found at %s — skipping "
            "auto-load. Use the Import Catalog wizard to load manually.",
            catalog_path)
        return

    with open(catalog_path, 'r', encoding='utf-8') as fh:
        raw = fh.read()

    Wizard = env['softg.bazaraki.import.wizard']
    rubrics, districts = Wizard._parse(raw)

    Rubric = env['softg.bazaraki.rubric']
    District = env['softg.bazaraki.district']

    # Only load if catalog is empty (don't trample user edits on reinstall)
    if Rubric.search_count([]) == 0:
        for r in rubrics:
            Rubric.create(r)
        _logger.info("Loaded %d Bazaraki rubrics from default catalog",
                     len(rubrics))
    else:
        _logger.info("Bazaraki rubric catalog already populated; skipping load")

    if District.search_count([]) == 0:
        for d in districts:
            District.create(d)
        _logger.info("Loaded %d Bazaraki districts from default catalog",
                     len(districts))
    else:
        _logger.info("Bazaraki district catalog already populated; skipping load")
