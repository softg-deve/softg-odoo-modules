from . import models


def post_init_hook(env):
    config = env['website.preheader.config'].sudo().get_config()

    # Assign any orphan messages to the config
    orphans = env['website.preheader.message'].sudo().search([('config_id', '=', False)])
    if orphans:
        orphans.write({'config_id': config.id})

    # Create default messages only on fresh install (no messages yet)
    if not config.message_ids:
        env['website.preheader.message'].sudo().create([
            {
                'name': '👋 Welcome! Customize your ticker at Website → Configuration → Preheader Ticker',
                'sequence': 10,
                'config_id': config.id,
            },
            {
                'name': '🌐 softg.dev',
                'href': 'https://softg.dev',
                'sequence': 20,
                'config_id': config.id,
            },
            {
                'name': 'support@softg.dev',
                'href': 'mailto:support@softg.dev',
                'sequence': 30,
                'config_id': config.id,
            },
            {
                'name': '+357 96699649',
                'href': 'tel:+35796699649',
                'sequence': 40,
                'config_id': config.id,
            },
        ])
