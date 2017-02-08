# -*- coding: utf-8 -*-
# Copyright (C) 2016 KMEE (http://www.kmee.com.br)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import api, fields, models, exceptions, _
from datetime import datetime

MES_DO_ANO = [
    (1, u'Jan'),
    (2, u'Fev'),
    (3, u'Mar'),
    (4, u'Abr'),
    (5, u'Mai'),
    (6, u'Jun'),
    (7, u'Jul'),
    (8, u'Ago'),
    (9, u'Set'),
    (10, u'Out'),
    (11, u'Nov'),
    (12, u'Dez'),
]


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.multi
    def _valor_total_folha(self):
        total = 0.00
        for line in self.line_ids:
            total += line.valor_provento - line.valor_deducao
        self.write({'total_folha': total})

    employee_id_readonly = fields.Many2one(
        string=u'Funcionário',
        comodel_name='hr.employee',
        compute='set_employee_id',
    )

    @api.depends('line_ids')
    @api.model
    def _buscar_payslip_line(self):
        lines = []
        for line in self.line_ids:
            if line.valor_provento or line.valor_deducao:
                lines.append(line.id)
        self.line_resume_ids = lines

    struct_id_readonly = fields.Many2one(
        string=u'Estrutura de Salário',
        comodel_name='hr.payroll.structure',
        compute='set_employee_id',
    )

    mes_do_ano = fields.Selection(
        selection=MES_DO_ANO,
        string=u'Mês',
        required=True,
        default=datetime.now().month,
    )

    ano = fields.Integer(
        string=u'Ano',
        default=datetime.now().year,
    )

    total_folha = fields.Float(
        string="Total",
        default=0.00
    )

    line_resume_ids = fields.One2many(
        comodel_name='hr.payslip.line',
        inverse_name='slip_id',
        compute=_buscar_payslip_line,
        string="Holerite Resumo",
    )

    def get_attendances(self, nome, sequence, code, number_of_days,
                        number_of_hours, contract_id):
        attendance = {
            'name': nome,
            'sequence': sequence,
            'code': code,
            'number_of_days': number_of_days,
            'number_of_hours': number_of_hours,
            'contract_id': contract_id.id,
        }
        return attendance

    @api.multi
    def get_worked_day_lines(self, contract_id, date_from, date_to):
        """
        @param contract_ids: list of contract id
        @return: returns a list of dict containing the input that should
        be applied for the given contract between date_from and date_to
        """
        result = []
        for contract_id in self.env['hr.contract'].browse(contract_id):

            # get dias Base para cálculo do mês
            dias_mes = self.env['resource.calendar'].get_dias_base(
                fields.Datetime.from_string(date_from),
                fields.Datetime.from_string(date_to)
            )
            result += [self.get_attendances(u'Dias Base', 1, u'DIAS_BASE',
                                            dias_mes, 0.0, contract_id)]

            # get dias uteis
            dias_uteis = self.env['resource.calendar'].quantidade_dias_uteis(
                fields.Datetime.from_string(date_from),
                fields.Datetime.from_string(date_to),
            )
            result += [self.get_attendances(u'Dias Úteis', 2, u'DIAS_UTEIS',
                                            dias_uteis, 0.0, contract_id)]
            # get faltas
            leaves = {}
            hr_contract = self.env['hr.contract'].browse(contract_id.id)
            leaves = self.env['resource.calendar'].get_ocurrences(
                hr_contract.employee_id.id, date_from, date_to)
            if leaves.get('faltas_nao_remuneradas'):
                qtd_leaves = leaves['quantidade_dias_faltas_nao_remuneradas']
                result += [self.get_attendances(u'Faltas Não remuneradas', 3,
                                                u'FALTAS_NAO_REMUNERADAS',
                                                qtd_leaves,
                                                0.0, contract_id)]
            # get Quantidade de DSR
            quantity_DSR = hr_contract.working_hours. \
                quantidade_de_DSR(date_from, date_to)
            if quantity_DSR:
                result += [self.get_attendances(u'DSR do Mês', 4,
                                                u'DSR_TOTAL', quantity_DSR,
                                                0.0, contract_id)]
            # get discount DSR
            quantity_DSR_discount = self.env['resource.calendar']. \
                get_quantity_discount_DSR(leaves['faltas_nao_remuneradas'],
                                          hr_contract.working_hours.leave_ids,
                                          date_from, date_to)
            if leaves.get('faltas_nao_remuneradas'):
                result += [self.get_attendances(u'DSR a serem descontados', 5,
                                                u'DSR_PARA_DESCONTAR',
                                                quantity_DSR_discount,
                                                0.0, contract_id)]
            # get dias de férias + get dias de abono pecuniario
            quantidade_dias_ferias, quantidade_dias_abono = \
                self.env['resource.calendar'].get_quantidade_dias_ferias(
                    hr_contract.employee_id.id, date_from, date_to)

            result += [
                self.get_attendances(
                    u'Quantidade dias em Férias', 6, u'FERIAS',
                    quantidade_dias_ferias, 0.0, contract_id
                )
            ]

            result += [
                self.get_attendances(
                    u'Quantidade dias Abono Pecuniario', 7,
                    u'ABONO_PECUNIARIO', quantidade_dias_abono,
                    0.0, contract_id
                )
            ]

            # get Dias Trabalhados
            quantidade_dias_trabalhados = \
                dias_mes - leaves['quantidade_dias_faltas_nao_remuneradas'] - \
                quantity_DSR_discount - quantidade_dias_ferias
            result += [self.get_attendances(u'Dias Trabalhados', 34,
                                            u'DIAS_TRABALHADOS',
                                            quantidade_dias_trabalhados,
                                            0.0, contract_id)]
        return result

    @api.model
    def get_inputs(self, contract_ids, date_from, date_to):
        res = super(HrPayslip, self).get_inputs(
            contract_ids, date_from, date_to
        )
        contract = self.env['hr.contract'].browse(contract_ids)
        salario_mes_dic = {
            'name': 'Salário Mês',
            'code': 'SALARIO_MES',
            'amount': contract._salario_mes(date_from, date_to),
            'contract_id': contract.id,
        }
        salario_dia_dic = {
            'name': 'Salário Dia',
            'code': 'SALARIO_DIA',
            'amount': contract._salario_dia(date_from, date_to),
            'contract_id': contract.id,
        }
        salario_hora_dic = {
            'name': 'Salário Hora',
            'code': 'SALARIO_HORA',
            'amount': contract._salario_hora(date_from, date_to),
            'contract_id': contract.id,
        }
        res += [salario_mes_dic]
        res += [salario_dia_dic]
        res += [salario_hora_dic]
        return res

    def INSS(self, BASE_INSS):
        tabela_inss_obj = self.env['l10n_br.hr.social.security.tax']
        if BASE_INSS:
            inss = tabela_inss_obj._compute_inss(BASE_INSS, self.date_from)
            return inss
        else:
            return 0

    def IRRF(self, BASE_IR, BASE_INSS):
        tabela_irrf_obj = self.env['l10n_br.hr.income.tax']
        if BASE_INSS and BASE_IR:
            inss = self.INSS(BASE_INSS)
            irrf = tabela_irrf_obj._compute_irrf(
                BASE_IR, self.employee_id.id, inss, self.date_from
            )
            return irrf
        else:
            return 0

    @api.model
    def get_contract_specific_rubrics(self, contract_id, rule_ids):
        contract = self.env['hr.contract'].browse(contract_id.id)
        for rule in contract.specific_rule_ids:
            if datetime.strftime(
                    datetime.now(), '%Y-%m-%d') >= rule.date_start:
                if not rule.date_stop or datetime.strftime(
                        datetime.now(), '%Y-%m-%d') <= rule.date_stop:
                    rule_ids.append((rule.rule_id.id, rule.rule_id.sequence))
        return rule_ids

    @api.model
    def get_specific_rubric_value(self, rubrica_id):
        for rubrica in self.contract_id.specific_rule_ids:
            if rubrica.rule_id.id == rubrica_id:
                return rubrica.specific_quantity * \
                    rubrica.specific_percentual/100 * \
                    rubrica.specific_amount

    @api.multi
    def _buscar_valor_salario(self, codigo):
        for tipo_salario in self.input_line_ids:
            if tipo_salario.code == codigo:
                return tipo_salario.amount
        return 0.00

    @api.multi
    def _get_rat_fap_period_values(self, year):
        rat_fap_obj = self.env['l10n_br.hr.rat.fap']
        rat_fap = rat_fap_obj = rat_fap_obj.search(
            [('year', '=', year), ('company_id', '=', self.company_id.id)]
        )
        if rat_fap:
            return rat_fap
        else:
            raise exceptions.Warning(
                _('Can\'t find this year values in Rat Fap Table')
            )

    @api.multi
    def get_payslip_lines(self, payslip_id):
        """
        get_payslip_lines(cr, uid, contract_ids, payslip.id, context=context)]
        Na chamada da função o contract_ids é passado como active_ids (ids) e
         o id fo payslip é passado no parâmettro do payslip
        :param payslip_id: Id do payslip corrente
                self : Id do contract
        :return:
        """
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(
                    localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = \
                category.code in localdict['categories'].dict and \
                localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, employee_id, dict):
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code,
            mainly for usability purposes"""
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.env.cr.execute(
                    "SELECT sum(amount) as sum "
                    "FROM hr_payslip as hp, hr_payslip_input as pi "
                    "WHERE hp.employee_id = %s AND hp.state = 'done' "
                    "AND hp.date_from >= %s AND hp.date_to <= %s "
                    "AND hp.id = pi.payslip_id AND pi.code = %s",
                    (self.employee_id, from_date, to_date, code))
                res = self.env.cr.fetchone()[0]
                return res or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly
            for usability purposes"""
            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.env.cr.execute(
                    "SELECT sum(number_of_days) as number_of_days, "
                    "sum(number_of_hours) as number_of_hours "
                    "FROM hr_payslip as hp, hr_payslip_worked_days as pi "
                    "WHERE hp.employee_id = %s AND hp.state = 'done' "
                    "AND hp.date_from >= %s AND hp.date_to <= %s "
                    "AND hp.id = pi.payslip_id AND pi.code = %s",
                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code,
            mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.env.cr.execute(
                    "SELECT sum(case when hp.credit_note = False "
                    "then (pl.total) else (-pl.total) end) "
                    "FROM hr_payslip as hp, hr_payslip_line as pl "
                    "WHERE hp.employee_id = %s AND hp.state = 'done' "
                    "AND hp.date_from >= %s AND hp.date_to <= %s "
                    "AND hp.id = pl.slip_id AND pl.code = %s",
                    (self.employee_id, from_date, to_date, code))
                res = self.env.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten
        # by another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.env['hr.payslip']
        obj_rule = self.env['hr.salary.rule']
        payslip = payslip_obj.browse(payslip_id)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        input_obj = InputLine(payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(payslip.employee_id.id, rules)
        categories_obj = \
            BrowsableObject(payslip.employee_id.id, categories_dict)

        salario_mes = payslip._buscar_valor_salario('SALARIO_MES')
        salario_dia = payslip._buscar_valor_salario('SALARIO_DIA')
        salario_hora = payslip._buscar_valor_salario('SALARIO_HORA')
        rat_fap = payslip._get_rat_fap_period_values(payslip.ano)
        baselocaldict = {
            'CALCULAR': payslip, 'BASE_INSS': 0.0, 'BASE_FGTS': 0.0,
            'BASE_IR': 0.0, 'categories': categories_obj, 'rules': rules_obj,
            'payslip': payslip_obj, 'worked_days': worked_days_obj,
            'inputs': input_obj, 'rubrica': None, 'SALARIO_MES': salario_mes,
            'SALARIO_DIA': salario_dia, 'SALARIO_HORA': salario_hora,
            'RAT_FAP': rat_fap,
        }

        for contract_ids in self:
            # get the ids of the structures on the contracts
            # and their parent id as well
            structure_ids = self.env['hr.contract'].browse(
                contract_ids.ids).get_all_structures()

            # get the rules of the structure and thier children
            rule_ids = self.env['hr.payroll.structure'].browse(
                structure_ids).get_all_rules()
            rule_ids = self.get_contract_specific_rubrics(
                contract_ids, rule_ids)

            # run the rules by sequence
            sorted_rule_ids = \
                [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

            for contract in self.env['hr.contract'].browse(contract_ids.ids):
                employee = contract.employee_id
                localdict = dict(
                    baselocaldict, employee=employee, contract=contract)
                for rule in obj_rule.browse(sorted_rule_ids):
                    key = rule.code + '-' + str(contract.id)
                    localdict['result'] = None
                    localdict['result_qty'] = 1.0
                    localdict['result_rate'] = 100
                    localdict['rubrica'] = rule
                    # check if the rule can be applied
                    if obj_rule.satisfy_condition(rule.id, localdict) \
                            and rule.id not in blacklist:
                        # compute the amount of the rule
                        amount, qty, rate = \
                            obj_rule.compute_rule(rule.id, localdict)
                        # check if there is already a rule computed
                        # with that code
                        previous_amount = \
                            rule.code in localdict and \
                            localdict[rule.code] or 0.0
                        # set/overwrite the amount computed
                        # for this rule in the localdict
                        tot_rule = amount * qty * rate / 100.0
                        localdict[rule.code] = tot_rule
                        rules[rule.code] = rule
                        if rule.category_id.code == 'DEDUCAO':
                            if rule.compoe_base_INSS:
                                localdict['BASE_INSS'] -= tot_rule
                            if rule.compoe_base_IR:
                                localdict['BASE_IR'] -= tot_rule
                            if rule.compoe_base_FGTS:
                                localdict['BASE_FGTS'] -= tot_rule
                        else:
                            if rule.compoe_base_INSS:
                                localdict['BASE_INSS'] += tot_rule
                            if rule.compoe_base_IR:
                                localdict['BASE_IR'] += tot_rule
                            if rule.compoe_base_FGTS:
                                localdict['BASE_FGTS'] += tot_rule
                        # sum the amount for its salary category
                        localdict = _sum_salary_rule_category(
                            localdict, rule.category_id,
                            tot_rule - previous_amount)
                        # create/overwrite the rule in the temporary results
                        result_dict[key] = {
                            'salary_rule_id': rule.id,
                            'contract_id': contract.id,
                            'name': rule.name,
                            'code': rule.code,
                            'category_id': rule.category_id.id,
                            'sequence': rule.sequence,
                            'appears_on_payslip': rule.appears_on_payslip,
                            'condition_select': rule.condition_select,
                            'condition_python': rule.condition_python,
                            'condition_range': rule.condition_range,
                            'condition_range_min': rule.condition_range_min,
                            'condition_range_max': rule.condition_range_max,
                            'amount_select': rule.amount_select,
                            'amount_fix': rule.amount_fix,
                            'amount_python_compute':
                                rule.amount_python_compute,
                            'amount_percentage': rule.amount_percentage,
                            'amount_percentage_base':
                                rule.amount_percentage_base,
                            'register_id': rule.register_id.id,
                            'amount': amount,
                            'employee_id': contract.employee_id.id,
                            'quantity': qty,
                            'rate': rate,
                        }
                    else:
                        rules_seq = rule._model._recursive_search_of_rules(
                            self._cr, self._uid, rule, self._context)
                        blacklist += [id for id, seq in rules_seq]

            result = [value for code, value in result_dict.items()]
            return result

    def _computar_ano(self):
        ano = datetime.now().year
        return ano

    @api.multi
    def onchange_employee_id(self, date_from, date_to, contract_id):
        worked_days_obj = self.env['hr.payslip.worked_days']
        input_obj = self.env['hr.payslip.input']

        # delete old worked days lines
        old_worked_days_ids = worked_days_obj.search(
            [('payslip_id', '=', self.id)]
        )
        if old_worked_days_ids:
            for worked_day_id in old_worked_days_ids:
                worked_day_id.unlink()

        # delete old input lines
        old_input_ids = input_obj.search([('payslip_id', '=', self.id)])
        if old_input_ids:
            for input_id in old_input_ids:
                input_id.unlink()

        # defaults
        res = {
            'value': {
                'line_ids': [],
                'input_line_ids': [],
                'worked_days_line_ids': [],
                'name': '',
            }
        }
        # computation of the salary input
        worked_days_line_ids = self.get_worked_day_lines(
            contract_id, date_from, date_to
        )
        input_line_ids = self.get_inputs(contract_id, date_from, date_to)
        res['value'].update(
            {
                'worked_days_line_ids': worked_days_line_ids,
                'input_line_ids': input_line_ids,
            }
        )
        return res

    @api.multi
    @api.onchange('contract_id')
    def set_employee_id(self):
        for record in self:
            record.struct_id = record.contract_id.struct_id
            record.struct_id_readonly = record.struct_id
            self.set_dates()
            if record.contract_id:
                record.employee_id = record.contract_id.employee_id
                record.employee_id_readonly = record.employee_id

    @api.multi
    @api.onchange('mes_do_ano')
    def buscar_datas_periodo(self):
        for record in self:
            record.set_dates()
            if record.contract_id:
                record.onchange_employee_id(
                    record.date_from, record.date_to, record.contract_id.id
                )

    def set_dates(self):
        for record in self:
            ultimo_dia_do_mes = self.env['resource.calendar']. \
                get_ultimo_dia_mes(record.mes_do_ano, record.ano)

            primeiro_dia_do_mes = \
                datetime.strptime(str(record.mes_do_ano) + '-' +
                                  str(record.ano), '%m-%Y')

            if not record.contract_id.date_start:
                continue

            date_start = record.contract_id.date_start

            if str(primeiro_dia_do_mes) < date_start:
                date_from = record.contract_id.date_start
            else:
                date_from = str(primeiro_dia_do_mes)

            record.date_from = date_from

            date_end = record.contract_id.date_end

            if not date_end:
                record.date_to = str(ultimo_dia_do_mes)
            elif str(ultimo_dia_do_mes) > record.contract_id.date_end:
                record.date_to = record.contract_id.date_end
            else:
                record.date_to = str(ultimo_dia_do_mes)

    @api.multi
    def compute_sheet(self):
        super(HrPayslip, self).compute_sheet()
        self._valor_total_folha()
        return True


class HrPayslipeLine(models.Model):
    _inherit = "hr.payslip.line"

    @api.model
    def _valor_provento(self):
        for record in self:
            if record.salary_rule_id.category_id.code == "PROVENTO":
                record.valor_provento = record.total
            else:
                record.valor_provento = 0.00

    @api.model
    def _valor_deducao(self):
        for record in self:
            if record.salary_rule_id.category_id.code in ["DEDUCAO"] \
                    or record.salary_rule_id.code == "INSS" \
                    or record.salary_rule_id.code == "IRPF":
                record.valor_deducao = record.total
            else:
                record.valor_deducao = 0.00

    valor_provento = fields.Float(
        string="Provento",
        compute=_valor_provento,
        default=0.00,
    )
    valor_deducao = fields.Float(
        string="Dedução",
        compute=_valor_deducao,
        default=0.00,
    )