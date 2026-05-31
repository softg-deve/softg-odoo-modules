from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_customer_statement_data(self, date_from, date_to, company_id):
        """Returns posted move lines for a partner in the given date range."""
        self.ensure_one()
        domain = [
            ('partner_id', '=', self.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company_id),
        ]
        return self.env['account.move.line'].search(domain, order='date asc, move_id asc')

    def _get_customer_statement_opening_balance(self, date_from, company_id):
        """Returns the sum of all posted receivable/payable moves before date_from."""
        self.ensure_one()
        domain = [
            ('partner_id', '=', self.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('move_id.state', '=', 'posted'),
            ('date', '<', date_from),
            ('company_id', '=', company_id),
        ]
        lines = self.env['account.move.line'].search(domain)
        return sum(lines.mapped('balance'))


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, *args, **kwargs):
        if self.ids and self.report_name == 'customer_statement_report_and_email.report_customer_statement_document':
            return super().with_context(cs_report=True)._run_wkhtmltopdf(*args, **kwargs)
        return super()._run_wkhtmltopdf(*args, **kwargs)

    def _build_wkhtmltopdf_args(self, *args, **kwargs):
        result = super()._build_wkhtmltopdf_args(*args, **kwargs)
        if '--encoding' not in result:
            result.extend(['--encoding', 'utf-8'])
        if self.env.context.get('cs_report'):
            result.extend(['--margin-top', '5'])
            result.extend(['--footer-center', 'Page [page] of [topage]'])
            result.extend(['--footer-font-size', '9'])
            result.extend(['--footer-spacing', '5'])
        return result
