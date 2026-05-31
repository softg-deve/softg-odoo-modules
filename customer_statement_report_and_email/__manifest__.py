{
    'name': 'Customer Statement Report',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Reporting',
    'summary': 'Professional Customer Statement PDF with Bulk Email — send statements to all customers in one click',
    'description': """
Customer Statement Report
=========================
Generate and send professional customer account statements directly from Odoo Accounting.

Features:
- PDF statement per customer: invoices, opening balance, due dates, overdue highlighting
- Single or multi-customer selection — print one PDF or download a ZIP of all
- Send by Email — single customer opens Odoo compose dialog
- Bulk Email Wizard — review all customers, filter by balance (positive/negative/zero), send in one click
- Dynamic bank account section pulled from company settings
- Statement Date field (independent from period dates)
- UTF-8 / Unicode / Greek character support via DejaVu Sans
- Page numbers in PDF footer via wkhtmltopdf

Accessible via: Accounting → Reporting → Customer Statement
    """,
    'author': 'SoftG',
    'website': 'https://www.softg.dev',
    'support': 'support@softg.dev',
    'license': 'OPL-1',
    'price': 49.99,
    'currency': 'EUR',
    'depends': ['account', 'account_reports'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/customer_statement_wizard_views.xml',
        'wizard/customer_statement_bulk_wizard_views.xml',
        'report/customer_statement_report_and_email.xml',
        'report/customer_statement_templates.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
