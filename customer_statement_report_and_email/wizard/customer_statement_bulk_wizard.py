import base64
from odoo import models, fields, api
from odoo.exceptions import UserError


class CustomerStatementBulkEmailLine(models.TransientModel):
    _name = 'customer.statement.bulk.email.line'
    _description = 'Bulk Email Line'

    wizard_id = fields.Many2one('customer.statement.bulk.email.wizard', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer')
    email = fields.Char(string='Email')
    outstanding_balance = fields.Float(string='Balance', digits=(16, 2))
    sequence = fields.Integer(string='#')
    include = fields.Boolean(string='Send', default=True)


class CustomerStatementBulkEmailWizard(models.TransientModel):
    _name = 'customer.statement.bulk.email.wizard'
    _description = 'Customer Statement Bulk Email'

    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    statement_date = fields.Date(string='Statement Date', required=True)
    company_id = fields.Many2one('res.company', required=True)
    line_ids = fields.One2many('customer.statement.bulk.email.line', 'wizard_id',
                               string='Customers')
    total_count = fields.Integer(compute='_compute_counts')
    will_send_count = fields.Integer(compute='_compute_counts')
    no_email_count = fields.Integer(compute='_compute_counts')
    total_positive_balance = fields.Float(compute='_compute_counts', digits=(16, 2))
    total_negative_balance = fields.Float(compute='_compute_counts', digits=(16, 2))

    @api.depends('line_ids', 'line_ids.include', 'line_ids.email', 'line_ids.outstanding_balance')
    def _compute_counts(self):
        for rec in self:
            rec.total_count = len(rec.line_ids)
            rec.will_send_count = len(rec.line_ids.filtered(lambda l: l.include and l.email))
            rec.no_email_count = len(rec.line_ids.filtered(lambda l: not l.email))
            rec.total_positive_balance = sum(
                rec.line_ids.filtered(lambda l: l.outstanding_balance > 0).mapped('outstanding_balance'))
            rec.total_negative_balance = abs(sum(
                rec.line_ids.filtered(lambda l: l.outstanding_balance < 0).mapped('outstanding_balance')))

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_select_all(self):
        self.line_ids.write({'include': True})
        return self._reopen()

    def action_unselect_all(self):
        self.line_ids.write({'include': False})
        return self._reopen()

    def action_select_positive(self):
        self.line_ids.filtered(lambda l: l.outstanding_balance > 0).write({'include': True})
        self.line_ids.filtered(lambda l: l.outstanding_balance <= 0).write({'include': False})
        return self._reopen()

    def action_select_negative(self):
        self.line_ids.filtered(lambda l: l.outstanding_balance < 0).write({'include': True})
        self.line_ids.filtered(lambda l: l.outstanding_balance >= 0).write({'include': False})
        return self._reopen()

    def action_select_zero(self):
        self.line_ids.filtered(lambda l: l.outstanding_balance == 0).write({'include': True})
        self.line_ids.filtered(lambda l: l.outstanding_balance != 0).write({'include': False})
        return self._reopen()

    def _build_bulk_email_body(self, partner):
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

    def action_send_all(self):
        lines_to_send = self.line_ids.filtered(lambda l: l.include and l.email)
        lines_no_email = self.line_ids.filtered(lambda l: l.include and not l.email)

        if not lines_to_send:
            raise UserError(
                'No customers with email addresses selected. '
                'Please add email addresses to customer records first.')

        report_xmlid = 'customer_statement_report_and_email.action_report_customer_statement'
        sent = []

        for line in lines_to_send:
            partner = line.partner_id
            single = self.env['customer.statement.wizard'].create({
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
                'body_html': self._build_bulk_email_body(partner),
                'email_to': partner.email,
                'reply_to': self.company_id.email or '',
                'attachment_ids': [(4, attachment.id)],
            }).send()
            sent.append(partner.name)

        msg = 'Sent to {} customer(s).'.format(len(sent))
        if lines_no_email:
            skipped = ', '.join(lines_no_email.mapped('partner_id.name'))
            msg += ' Skipped (no email): {}.'.format(skipped)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Email Complete',
                'message': msg,
                'type': 'success' if sent else 'warning',
                'sticky': True,
            },
        }
