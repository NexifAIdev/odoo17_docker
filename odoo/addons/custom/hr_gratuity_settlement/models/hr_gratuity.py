# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError

date_format = "%Y-%m-%d"


class HrGratuity(models.Model):
    _name = 'hr.gratuity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Employee Gratuity"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled')],
        default='draft', tracking=True, string="State", help="State")
    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True,
                       default=lambda self: _('New'), help="Name")
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, help="Employee")
    employee_contract_type = fields.Selection([
        ('limited', 'Limited'),
        ('unlimited', 'Unlimited')], string='Contract Type', readonly=True,
        store=True, help="Choose the contract type."
                         "if contract type is limited then during gratuity"
                         "settlement if you have not specify the end date for"
                         "contract, gratuity configration of limited type will"
                         "be taken or if contract type is Unlimited then "
                         "during gratuity settlement if you have specify the"
                         "end date for contract, gratuity configration of"
                         "limited type will be taken.")
    employee_joining_date = fields.Date(string='Joining Date', readonly=True,
                                        store=True,
                                        help="Employee joining date")
    wage_type = fields.Selection(
        [('monthly', 'Monthly Fixed Wage'), ('hourly', 'Hourly Wage')],
        help="Select the wage type monthly or hourly")
    total_working_years = fields.Float(string='Total Years Worked',
                                       readonly=True, store=True,
                                       help="Total working years")
    employee_probation_years = fields.Float(string='Leaves Taken(Years)',
                                            readonly=True, store=True,
                                            help="Employee probation years")
    employee_gratuity_years = fields.Float(string='Gratuity Calculation Years',
                                           readonly=True, store=True,
                                           help="Employee gratuity years")
    employee_basic_salary = fields.Float(string='Basic Salary',
                                         readonly=True,
                                         help="Employee's basic salary.")
    employee_gratuity_duration_id = fields.Many2one('gratuity.configuration',
                                                    readonly=True,
                                                    string='Configuration Line',
                                                    help="Employee gratuity"
                                                         " duration")
    employee_gratuity_configuration_id = fields.Many2one(
        'hr.gratuity.accounting.configuration',
        readonly=True,
        string='Gratuity Configuration', help="Gratuity configuration")
    employee_gratuity_amount = fields.Float(string='Gratuity Payment',
                                            readonly=True, store=True,
                                            help="Gratuity amount for the"
                                                 "employee. it is calculated"
                                                 "If the wage type is hourly"
                                                 "then gratuity payment is"
                                                 "calculated as employee basic"
                                                 "salary * Employee Daily Wage "
                                                 "Days * gratuity configration "
                                                 "rule percentage * gratuity "
                                                 "calculation years.orIf the "
                                                 "wage type is monthly then "
                                                 "gratuity payment is calcula"
                                                 "ted as employee basic salary "
                                                 "* (Working Days/Employee"
                                                 "Daily Wage Days) * gratuity"
                                                 "configration rule percentage"
                                                 "* gratuity calculation years")
    hr_gratuity_credit_account_id = fields.Many2one('account.account',
                                                help="Gratuity credit account")
    hr_gratuity_debit_account_id = fields.Many2one('account.account',
                                                help="Gratuity debit account")
    hr_gratuity_journal_id = fields.Many2one('account.journal',
                                             help="Gratuity journal")
    company_id = fields.Many2one('res.company', 'Company', required=True,
                                 default=lambda self: self.env.company,
                                 help="Company")
    currency_id = fields.Many2one(related="company_id.currency_id",
                                  string="Currency", readonly=True,
                                  help="Currency")

    @api.model
    def create(self, vals):
        """ assigning the sequence for the record """
        vals['name'] = self.env['ir.sequence'].next_by_code('hr.gratuity')
        return super(HrGratuity, self).create(vals)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """ calculating the gratuity pay based on the contract and gratuity
        configurations """
        if self.employee_id.id:
            current_date = date.today()
            probation_ids = self.env['hr.training'].search(
                [('employee_id', '=', self.employee_id.id)])
            contract_ids = self.env['hr.contract'].search(
                [('employee_id', '=', self.employee_id.id)])
            contract_sorted = contract_ids.sorted(lambda line: line.date_start)
            if not contract_sorted:
                raise UserError(
                    _('No contracts found for the selected employee...!\n'
                      'Employee must have at least one contract to compute'
                      ' gratuity settlement.'))
            self.employee_joining_date = joining_date = contract_sorted[
                0].date_start
            employee_probation_days = 0
            # find total probation days
            for probation in probation_ids:
                start_date = probation.start_date
                end_date = probation.end_date
                employee_probation_days += (end_date - start_date).days
            # get running contract
            hr_contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', self.employee_id.id),
                 ('state', '=', 'open')])
            if len(hr_contract_id) > 1 or not hr_contract_id:
                raise UserError(
                    _('Selected employee have multiple or no running contracts!'))
            self.wage_type = hr_contract_id.wage_type
            if self.wage_type == 'hourly':
                self.employee_basic_salary = hr_contract_id.hourly_wage
            else:
                self.employee_basic_salary = hr_contract_id.wage
            if hr_contract_id.date_end:
                self.employee_contract_type = 'limited'
                employee_working_days = (
                        hr_contract_id.date_end - joining_date).days
                self.total_working_years = employee_working_days / 365
                self.employee_probation_years = employee_probation_days / 365
                employee_gratuity_years = (employee_working_days -
                                           employee_probation_days) / 365
                self.employee_gratuity_years = employee_gratuity_years
            else:
                self.employee_contract_type = 'unlimited'
                employee_working_days = (current_date - joining_date).days
                self.total_working_years = employee_working_days / 365
                self.employee_probation_years = employee_probation_days / 365
                employee_gratuity_years = (employee_working_days -
                                           employee_probation_days) / 365
                self.employee_gratuity_years = round(employee_gratuity_years, 2)
            gratuity_duration_id = False
            hr_accounting_configuration_id = self.env[
                'hr.gratuity.accounting.configuration'].search(
                [('active', '=', True),
                 ('config_contract_type', '=', self.employee_contract_type),
                 '|', ('gratuity_end_date', '>=', current_date),
                 ('gratuity_end_date', '=', False),
                 '|', ('gratuity_start_date', '<=', current_date),
                 ('gratuity_start_date', '=', False)])
            if len(hr_accounting_configuration_id) > 1:
                raise UserError(_(
                    "There is a date conflict in Gratuity accounting"
                    " configuration. "
                    "Please remove the conflict and try again!"))
            elif not hr_accounting_configuration_id:
                raise UserError(
                    _('No gratuity accounting configuration found '
                      'or please set proper start date and end date for '
                      'gratuity configuration!'))
            # find configuration ids related to the gratuity accounting
            # configuration
            self.employee_gratuity_configuration_id = (
                hr_accounting_configuration_id.id)
            conf_ids = hr_accounting_configuration_id.gratuity_configuration_table_ids.mapped(
                'id')
            hr_duration_config_ids = self.env['gratuity.configuration'].browse(
                conf_ids)
            for duration in hr_duration_config_ids:
                if (duration.from_year and duration.to_year and duration.
                        from_year <= self.total_working_years <= duration
                        .to_year):
                    gratuity_duration_id = duration
                    break
                elif (duration.from_year and not duration.to_year and duration.
                        from_year <= self.total_working_years):
                    gratuity_duration_id = duration
                    break
                elif (duration.to_year and not duration.from_year and self.
                        total_working_years <= duration.to_year):
                    gratuity_duration_id = duration
                    break
            if gratuity_duration_id:
                self.employee_gratuity_duration_id = gratuity_duration_id.id
            else:
                raise UserError(_('No suitable gratuity durations found !'))
            # show warning when the employee's working years is less than
            # one year or no running employee found.
            if self.total_working_years < 1 and self.employee_id.id:
                raise UserError(
                    _('Selected Employee is not eligible for Gratuity'
                      ' Settlement'))
            self.hr_gratuity_journal_id = (hr_accounting_configuration_id.
                                           gratuity_journal_id.id)
            self.hr_gratuity_credit_account_id = (
                hr_accounting_configuration_id.gratuity_credit_account_id.id)
            self.hr_gratuity_debit_account_id = (
                hr_accounting_configuration_id.gratuity_debit_account_id.id)
            if (self.employee_gratuity_duration_id and self.wage_type ==
                    'hourly'):
                if (self.employee_gratuity_duration_id.employee_working_days
                        != 0):
                    if (self.employee_id.resource_calendar_id and self.
                            employee_id.resource_calendar_id.hours_per_day):
                        daily_wage = (self.employee_basic_salary * self.
                                      employee_id.resource_calendar_id.
                                      hours_per_day)
                    else:
                        daily_wage = self.employee_basic_salary * 8
                    working_days_salary = (daily_wage * self.
                                           employee_gratuity_duration_id.
                                           employee_working_days)
                    gratuity_pay_per_year = (working_days_salary * self.
                                             employee_gratuity_duration_id.
                                             percentage)
                    employee_gratuity_amount = (gratuity_pay_per_year * self.
                                                employee_gratuity_years)
                    self.employee_gratuity_amount = round(
                        employee_gratuity_amount, 2)
                else:
                    raise UserError(
                        _("Employee working days is not configured in "
                          "the gratuity configuration..!"))
            elif (self.employee_gratuity_duration_id and self.wage_type
                  == 'monthly'):
                if (self.employee_gratuity_duration_id.employee_daily_wage_days
                        != 0):
                    daily_wage = (self.employee_basic_salary / self.
                                  employee_gratuity_duration_id.
                                  employee_daily_wage_days)
                    working_days_salary = (daily_wage * self.
                                           employee_gratuity_duration_id.
                                           employee_working_days)
                    gratuity_pay_per_year = (working_days_salary * self.
                                             employee_gratuity_duration_id.
                                             percentage)
                    employee_gratuity_amount = (gratuity_pay_per_year * self.
                                                employee_gratuity_years)
                    self.employee_gratuity_amount = round(
                        employee_gratuity_amount, 2)
                else:
                    raise UserError(_("Employee wage days is not configured in "
                                      "the gratuity configuration..!"))

    def submit_request(self):
        """
        Changing state to submit
        :return:
        """
        self.write({'state': 'submit'})

    def cancel_request(self):
        """
        Canceling the gratuity request
        :return:
        """
        self.write({'state': 'cancel'})

    def set_to_draft(self):
        """
        Set the canceled request to draft
        :return:
        """
        self.write({'state': 'draft'})

    def approved_request(self):
        """
        function for creating the account move with gratuity amount and
        account credentials
        """
        for hr_gratuity_id in self:
            debit_vals = {
                'name': hr_gratuity_id.employee_id.name,
                'account_id': hr_gratuity_id.hr_gratuity_debit_account_id.id,
                'partner_id': hr_gratuity_id.employee_id.address_id.id or
                              False,
                'journal_id': hr_gratuity_id.hr_gratuity_journal_id.id,
                'date': date.today(),
                'debit': hr_gratuity_id.employee_gratuity_amount > 0.0 and
                         hr_gratuity_id.employee_gratuity_amount or 0.0,
                'credit': hr_gratuity_id.employee_gratuity_amount < 0.0 and
                          -hr_gratuity_id.employee_gratuity_amount or 0.0,
            }
            credit_vals = {
                'name': hr_gratuity_id.employee_id.name,
                'account_id': hr_gratuity_id.hr_gratuity_credit_account_id.id,
                'partner_id': hr_gratuity_id.employee_id.address_id.id or
                              False,
                'journal_id': hr_gratuity_id.hr_gratuity_journal_id.id,
                'date': date.today(),
                'debit': hr_gratuity_id.employee_gratuity_amount < 0.0 and
                         -hr_gratuity_id.employee_gratuity_amount or 0.0,
                'credit': hr_gratuity_id.employee_gratuity_amount > 0.0 and
                          hr_gratuity_id.employee_gratuity_amount or 0.0,
            }
            vals = {
                'name': hr_gratuity_id.name + " - " + 'Gratuity for' + ' ' +
                        hr_gratuity_id.employee_id.name,
                'narration': hr_gratuity_id.employee_id.name,
                'ref': hr_gratuity_id.name,
                'partner_id': hr_gratuity_id.employee_id.address_id.id or
                              False,
                'journal_id': hr_gratuity_id.hr_gratuity_journal_id.id,
                'date': date.today(),
                'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)],
            }
            move = hr_gratuity_id.env['account.move'].create(vals)
            move.action_post()
        self.write({'state': 'approve'})
