import wizard
import pooler
import base64
import time
from tools import mod10r

ASK_FORM = """<?xml version="1.0"?>
<form string="BVR Import">
	<field name="file"/>
</form>"""

ASK_FIELDS = {
	'file': {
		'string': 'BVR file',
		'type': 'binary',
		'required': True,
	},
}

def _import(obj, cursor, user, data, context):
	pool = pooler.get_pool(cursor.dbname)
	statement_line_obj = pool.get('account.bank.statement.line')
	statement_reconcile_obj = pool.get('account.bank.statement.reconcile')
	move_line_obj = pool.get('account.move.line')
	property_obj = pool.get('ir.property')
	model_fields_obj = pool.get('ir.model.fields')
	attachment_obj = pool.get('ir.attachment')
	file = data['form']['file']
	statement_id = data['id']

	records = []
	total_amount = 0
	total_cost = 0
	find_total = False

	for lines in base64.decodestring(file).split("\n"):
		# Manage files without carriage return
		while lines:
			(line, lines) = (lines[:128], lines[128:])
			record = {}

			if line[0:3] in ('999', '995'):
				if find_total:
					raise wizard.except_wizard('Error',
							'Too much total record found!')
				find_total = True
				if lines:
					raise wizard.except_wizard('Error',
							'Record found after total record!')
				amount = float(line[39:50]) + (float(line[50:51]) / 100)
				cost = float(line[69:77]) + (float(line[77:78]) / 100)
				if line[2] == '5':
					amount *= -1
					cost *= -1

				if round(amount - total_amount, 2) >= 0.01 \
						or round(cost - total_cost, 2) >= 0.01:
					raise wizard.except_wizard('Error',
							'Total record different from the computed!')
				if int(line[51:63]) != len(records):
					raise wizard.except_wizard('Error',
							'Number record different from the computed!')
			else:
				record = {
					'reference': line[12:39],
					'amount': float(line[39:48]) + (float(line[48:49]) / 100),
					'date': time.strftime('%Y-%m-%d',
						time.strptime(line[65:71], '%y%m%j')),
					'cost': float(line[96:99]) + (float(line[99:100]) / 100),
				}

				if record['reference'] != mod10r(record['reference'][:-1]):
					raise wizard.except_wizard('Error',
							'Recursive mod10 is invalid for reference: %s' % \
									record['reference'])

				if line[2] == '5':
					record['amount'] *= -1
					record['cost'] *= -1
				total_amount += record['amount']
				total_cost += record['cost']
				records.append(record)

	model_fields_ids = model_fields_obj.search(cursor, user, [
		('name', 'in', ['property_account_receivable', 'property_account_payable']),
		('model', '=', 'res.partner'),
		], context=context)
	property_ids = property_obj.search(cursor, user, [
		('fields_id', 'in', model_fields_ids),
		('res_id', '=', False),
		], context=context)

	account_receivable = False
	account_payable = False
	for property in property_obj.browse(cursor, user, property_ids, context=context):
		if property.fields_id.name == 'property_account_receivable':
			account_receivable = int(property.value.split(',')[1])
		elif property.fields_id.name == 'property_account_payable':
			account_payable = int(property.value.split(',')[1])

	for record in records:
		# Remove the 11 first char because it can be adherent number
		# TODO check if 11 is the right number
		reference = record['reference'][11:-1].lstrip('0')
		values = {
			'name': 'BVR',
			'date': record['date'],
			'amount': record['amount'],
			'ref': reference,
			'type': (record['amount'] >= 0 and 'customer') or 'supplier',
			'statement_id': statement_id,
		}
		line_ids = move_line_obj.search(cursor, user, [
			('ref', '=', reference),
			('reconcile_id', '=', False),
			('account_id.type', 'in', ['receivable', 'payable']),
			], order='date DESC, id DESC', context=context)
		line2reconcile = False
		partner_id = False
		account_id = False
		for line in move_line_obj.browse(cursor, user, line_ids, context=context):
			if line.partner_id.id:
				partner_id = line.partner_id.id
			if record['amount'] >= 0:
				if round(record['amount'] - line.debit, 2) < 0.01:
					line2reconcile = line.id
					account_id = line.account_id.id
					break
			else:
				if round(line.credit + record['amount'], 2) < 0.01:
					line2reconcile = line.id
					account_id = line.account_id.id
					break
		if not account_id:
			if record['amount'] >= 0:
				account_id = account_receivable
			else:
				account_id = account_payable
		values['account_id'] = account_id
		values['partner_id'] = partner_id

		if line2reconcile:
			values['reconcile_id'] = statement_reconcile_obj.create(cursor, user, {
				'line_ids': [(6, 0, [line2reconcile])],
				}, context=context)
		statement_line_obj.create(cursor, user, values, context=context)
	attachment_obj.create(cursor, user, {
		'name': 'BVR',
		'datas': file,
		'datas_fname': 'BVR.txt',
		'res_model': 'account.bank.statement',
		'res_id': statement_id,
		}, context=context)
	return {}


class BVRImport(wizard.interface):
	states = {
		'init': {
			'actions': [],
			'result': {
				'type': 'form',
				'arch': ASK_FORM,
				'fields': ASK_FIELDS,
				'state': [
					('end', 'Cancel', 'gtk-cancel'),
					('import', 'Import', 'gtk-ok', True),
				],
			},
		},
		'import': {
			'actions': [],
			'result': {
				'type': 'action',
				'action': _import,
				'state': 'end',
			},
		},
	}

BVRImport('l10n_ch.bvr_import')
