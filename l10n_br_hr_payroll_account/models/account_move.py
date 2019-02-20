# -*- coding: utf-8 -*-
# Copyright (C) 2016 KMEE (http://www.kmee.com.br)
# Copyright (C) 2018 ABGF (http://www.abgf.gov.br)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from __future__ import absolute_import, print_function, unicode_literals

from openerp import models, fields, api


class AccountMove(models.Model):
    _inherit = b'account.move'

    payslip_id = fields.Many2one(
        comodel_name="hr.payslip",
        string="Payslip",
        ondelete='cascade',
    )

    payslip_autonomo_id = fields.Many2one(
        comodel_name="hr.payslip.autonomo",
        string="Payslip Autonomo",
        ondelete='cascade',
    )

    payslip_run_id = fields.Many2one(
        comodel_name="hr.payslip.run",
        string="Payslip Run",
        ondelete='cascade',
    )

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            if record.payslip_id or record.payslip_run_id:
                name = record.name
                res.append((record.id, name))

            if res:
                return res
            else:
                return super(AccountMove, self).name_get()
