from odoo import models, fields
from odoo.exceptions import UserError
import base64
from datetime import date


class CustomerStatementWizard(models.TransientModel):
    _name = 'customer.statement.wizard'
    _description = 'Customer Statement Wizard'

    date_from = fields.Date(string='From Date', required=True,
        default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='To Date', required=True,
        default=fields.Date.today)
    statement_date = fields.Date(string='Statement Date', required=True,
        default=fields.Date.today)
    partner_ids = fields.Many2many('res.partner', string='Customers',
        domain=[('customer_rank', '>', 0)],
        help='Leave empty to include all customers with transactions.')
    company_id = fields.Many2one('res.company', string='Company',
        required=True, default=lambda self: self.env.company)

    def _build_partner_data(self, partner):
        opening_balance = partner._get_customer_statement_opening_balance(
            self.date_from, self.company_id.id)

        domain = [
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        move_lines = self.env['account.move.line'].search(domain, order='date asc, move_id asc')
        lines_data = []
        total_invoices = 0.0
        total_payments = 0.0

        if opening_balance != 0:
            lines_data.append({
                'invoice_no': 'Opening Balance',
                'date': '',
                'due_date': '',
                'amount': opening_balance,
                'amount_fmt': '{:,.2f}'.format(opening_balance),
                'overdue': False,
                'is_opening': True,
            })
            if opening_balance > 0:
                total_invoices += opening_balance
            else:
                total_payments += abs(opening_balance)

        for ml in move_lines:
            amount = ml.balance
            if amount > 0:
                total_invoices += amount
            else:
                total_payments += abs(amount)
            invoice_no = ml.move_id.name or ''
            if ml.move_id.invoice_origin:
                invoice_no = '{} ({})'.format(invoice_no, ml.move_id.invoice_origin)
            lines_data.append({
                'invoice_no': invoice_no,
                'date': ml.date.strftime('%d/%m/%Y') if ml.date else '',
                'due_date': ml.date_maturity.strftime('%d/%m/%Y') if ml.date_maturity else '',
                'amount': amount,
                'amount_fmt': '{:,.2f}'.format(amount),
                'overdue': bool(ml.date_maturity and ml.date_maturity < date.today() and amount > 0),
                'is_opening': False,
            })

        outstanding = total_invoices - total_payments
        currency_symbol = self.company_id.currency_id.symbol or ''

        return {
            'partner_name': partner.name or '',
            'partner_street': partner.street or '',
            'partner_city': partner.city or '',
            'partner_zip': partner.zip or '',
            'partner_country': partner.country_id.name if partner.country_id else '',
            'partner_vat': partner.vat or '',
            'partner_phone': partner.phone or getattr(partner, 'mobile', '') or '',
            'currency_symbol': currency_symbol,
            'lines': lines_data,
            'total_invoices_fmt': '{:,.2f} {}'.format(total_invoices, currency_symbol),
            'total_payments_fmt': '{:,.2f} {}'.format(total_payments, currency_symbol),
            'outstanding_fmt': '{:,.2f} {}'.format(outstanding, currency_symbol),
        }

    def _get_all_report_data(self):
        """Called directly from the QWeb template."""
        if self.partner_ids:
            partners = self.partner_ids
        else:
            domain = [
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('company_id', '=', self.company_id.id),
            ]
            lines = self.env['account.move.line'].search(domain)
            partners = lines.mapped('partner_id').filtered(lambda p: p.name)
        report_data = []
        for partner in partners.sorted(key=lambda p: p.name):
            pdata = self._build_partner_data(partner)
            if pdata['lines']:
                report_data.append(pdata)
        return report_data

    def _build_email_body(self, partner):
        comp = self.company_id
        addr = ' '.join(x for x in [
            comp.street or '',
            comp.city or '',
            ((comp.state_id.code + ' ' + (comp.zip or '')) if comp.state_id else (comp.zip or '')),
            (comp.country_id.name if comp.country_id else ''),
        ] if x)

        phone1 = comp.phone or ''
        phone2 = getattr(comp, 'mobile', '') or ''
        email = comp.email or ''
        web = comp.website or ''
        web_href = web if web.startswith('http') else ('https://' + web if web else '')

        phones = []
        if phone1:
            phones.append('<a href="tel:{}" style="color:#555;text-decoration:none;">{}</a>'.format(
                phone1.replace(' ', ''), phone1))
        if phone2:
            phones.append('<a href="tel:{}" style="color:#555;text-decoration:none;">{}</a>'.format(
                phone2.replace(' ', ''), phone2))
        phones_html = ' | '.join(phones)

        sig = (
            '<hr style="border:none;border-top:1px solid #ddd;margin:20px 0 10px 0;"/>'
            '<p style="margin:0 0 2px 0;font-size:13px;color:#1B3460;font-weight:700;">'
            + (comp.name or '') +
            '</p>'
            '<p style="margin:0 0 3px 0;font-size:11px;color:#666;">' + addr + '</p>'
        )
        if email or web:
            sig += '<p style="margin:0 0 3px 0;font-size:11px;color:#555;">'
            if email:
                sig += 'Email: <a href="mailto:{0}" style="color:#555;text-decoration:none;">{0}</a>'.format(email)
            if email and web:
                sig += ' &nbsp;|&nbsp; '
            if web:
                sig += 'Website: <a href="{}" style="color:#555;text-decoration:none;">{}</a>'.format(web_href, web)
            sig += '</p>'
        if phones_html:
            sig += '<p style="margin:0 0 3px 0;font-size:11px;color:#555;">Phone: ' + phones_html + '</p>'

        return (
            '<p>Dear ' + partner.name + ',</p>'
            '<p>Please find attached your customer statement for the period '
            '<strong>' + self.date_from.strftime('%d/%m/%Y') + '</strong> to '
            '<strong>' + self.date_to.strftime('%d/%m/%Y') + '</strong>.</p>'
            '<p>If you have any questions please do not hesitate to contact us.</p>'
            '<p>Kind regards,</p>'
        ) + sig

    def action_send_by_email(self):
        """Send customer statement PDF by email to selected partners."""
        self.ensure_one()
        if not self.partner_ids:
            raise UserError('Please select at least one customer to send by email.')

        report_xmlid = 'customer_statement_report_and_email.action_report_customer_statement'

        # Single partner: open interactive compose dialog
        if len(self.partner_ids) == 1:
            partner = self.partner_ids[0]
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                report_xmlid, res_ids=[self.id])
            attachment = self.env['ir.attachment'].create({
                'name': 'Customer_Statement_{}_{}_to_{}.pdf'.format(
                    partner.name.replace(' ', '_'),
                    self.date_from.strftime('%d%m%Y'),
                    self.date_to.strftime('%d%m%Y'),
                ),
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mail.compose.message',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_subject': 'Customer Statement – {} to {}'.format(
                        self.date_from.strftime('%d/%m/%Y'),
                        self.date_to.strftime('%d/%m/%Y'),
                    ),
                    'default_body': self._build_email_body(partner),
                    'default_attachment_ids': [(4, attachment.id)],
                    'default_partner_ids': [(4, partner.id)] if partner.email else [],
                    'default_reply_to': self.company_id.email or '',
                },
            }

        # Multiple partners: auto-send to each
        sent = []
        no_email = []
        for partner in self.partner_ids:
            if not partner.email:
                no_email.append(partner.name)
                continue
            single = self.create({
                'partner_ids': [(6, 0, [partner.id])],
                'date_from': self.date_from,
                'date_to': self.date_to,
                'statement_date': self.statement_date,
                'company_id': self.company_id.id,
            })
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                report_xmlid, res_ids=[single.id])
            attachment = self.env['ir.attachment'].create({
                'name': 'Customer_Statement_{}_{}_to_{}.pdf'.format(
                    partner.name.replace(' ', '_'),
                    self.date_from.strftime('%d%m%Y'),
                    self.date_to.strftime('%d%m%Y'),
                ),
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'mimetype': 'application/pdf',
            })
            self.env['mail.mail'].create({
                'subject': 'Customer Statement – {} to {}'.format(
                    self.date_from.strftime('%d/%m/%Y'),
                    self.date_to.strftime('%d/%m/%Y'),
                ),
                'body_html': self._build_email_body(partner),
                'email_to': partner.email,
                'attachment_ids': [(4, attachment.id)],
            }).send()
            sent.append(partner.name)

        msg = 'Sent to: {}.'.format(', '.join(sent)) if sent else 'No emails sent.'
        if no_email:
            msg += ' No email on file for: {}.'.format(', '.join(no_email))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Statements Sent' if sent else 'Nothing Sent',
                'message': msg,
                'type': 'success' if sent else 'warning',
                'sticky': True,
            },
        }

    def action_bulk_email_prepare(self):
        """Find all customers with transactions in the period and open bulk email review."""
        domain = [
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        lines = self.env['account.move.line'].search(domain)
        partners = lines.mapped('partner_id').filtered(
            lambda p: p.name).sorted(key=lambda p: p.name)

        line_vals = []
        for partner in partners:
            bal_domain = [
                ('partner_id', '=', partner.id),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ('move_id.state', '=', 'posted'),
                ('date', '<=', self.date_to),
                ('company_id', '=', self.company_id.id),
            ]
            outstanding = sum(
                self.env['account.move.line'].search(bal_domain).mapped('balance'))
            line_vals.append({
                'sequence': len(line_vals) + 1,
                'partner_id': partner.id,
                'email': getattr(partner, 'email', '') or '',
                'outstanding_balance': outstanding,
                'include': True,
            })

        bulk = self.env['customer.statement.bulk.email.wizard'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'statement_date': self.statement_date,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, v) for v in line_vals],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bulk Email — Review Customers',
            'res_model': 'customer.statement.bulk.email.wizard',
            'res_id': bulk.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print_statement(self):
        self.ensure_one()
        report_xmlid = 'customer_statement_report_and_email.action_report_customer_statement'

        if len(self.partner_ids) <= 1:
            return self.env.ref(report_xmlid).report_action(self)

        # Multiple partners → one PDF per customer inside a ZIP
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for partner in self.partner_ids:
                single = self.create({
                    'partner_ids': [(6, 0, [partner.id])],
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'statement_date': self.statement_date,
                    'company_id': self.company_id.id,
                })
                pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    report_xmlid, res_ids=[single.id])
                safe_name = partner.name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                filename = 'Statement_{}_{}_to_{}.pdf'.format(
                    safe_name,
                    self.date_from.strftime('%d%m%Y'),
                    self.date_to.strftime('%d%m%Y'),
                )
                zf.writestr(filename, pdf_content)

        zip_buffer.seek(0)
        attachment = self.env['ir.attachment'].create({
            'name': 'Customer_Statements_{}_to_{}.zip'.format(
                self.date_from.strftime('%d%m%Y'),
                self.date_to.strftime('%d%m%Y'),
            ),
            'type': 'binary',
            'datas': base64.b64encode(zip_buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/zip',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}?download=true'.format(attachment.id),
            'target': 'self',
        }
