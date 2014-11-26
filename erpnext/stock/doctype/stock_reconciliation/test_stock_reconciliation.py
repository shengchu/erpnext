# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# ERPNext - web based ERP (http://erpnext.com)
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, unittest
from frappe.utils import flt
import json
from erpnext.accounts.utils import get_fiscal_year, get_stock_and_account_difference


class TestStockReconciliation(unittest.TestCase):
	def test_reco_for_fifo(self):
		frappe.defaults.set_global_default("auto_accounting_for_stock", 0)
		# [[qty, valuation_rate, posting_date,
		#		posting_time, expected_stock_value, bin_qty, bin_valuation]]
		input_data = [
			[50, 1000, "2012-12-26", "12:00", 50000, 45, 48000],
			[5, 1000, "2012-12-26", "12:00", 5000, 0, 0],
			[15, 1000, "2012-12-26", "12:00", 15000, 10, 12000],
			[25, 900, "2012-12-26", "12:00", 22500, 20, 22500],
			[20, 500, "2012-12-26", "12:00", 10000, 15, 18000],
			[50, 1000, "2013-01-01", "12:00", 50000, 65, 68000],
			[5, 1000, "2013-01-01", "12:00", 5000, 20, 23000],
			["", 1000, "2012-12-26", "12:05", 15000, 10, 12000],
			[20, "", "2012-12-26", "12:05", 16000, 15, 18000],
			[10, 2000, "2012-12-26", "12:10", 20000, 5, 6000],
			[1, 1000, "2012-12-01", "00:00", 1000, 11, 13200],
			[0, "", "2012-12-26", "12:10", 0, -5, -6000]
		]

		for d in input_data:
			self.cleanup_data()
			self.insert_existing_sle("FIFO")
			stock_reco = self.submit_stock_reconciliation(d[0], d[1], d[2], d[3])

			# check stock value
			res = frappe.db.sql("""select stock_value from `tabStock Ledger Entry`
				where item_code = '_Test Item' and warehouse = '_Test Warehouse - _TC'
				and posting_date = %s and posting_time = %s order by name desc limit 1""",
				(d[2], d[3]))
			self.assertEqual(res and flt(res[0][0]) or 0, d[4])

			# check bin qty and stock value
			bin = frappe.db.sql("""select actual_qty, stock_value from `tabBin`
				where item_code = '_Test Item' and warehouse = '_Test Warehouse - _TC'""")

			self.assertEqual(bin and [flt(bin[0][0]), flt(bin[0][1])] or [], [d[5], d[6]])

			# no gl entries
			gl_entries = frappe.db.sql("""select name from `tabGL Entry`
				where voucher_type = 'Stock Reconciliation' and voucher_no = %s""",
				 stock_reco.name)
			self.assertFalse(gl_entries)


	def test_reco_for_moving_average(self):
		frappe.defaults.set_global_default("auto_accounting_for_stock", 0)
		# [[qty, valuation_rate, posting_date,
		#		posting_time, expected_stock_value, bin_qty, bin_valuation]]
		input_data = [
			[50, 1000, "2012-12-26", "12:00", 50000, 45, 48000],
			[5, 1000, "2012-12-26", "12:00", 5000, 0, 0],
			[15, 1000, "2012-12-26", "12:00", 15000, 10, 11500],
			[25, 900, "2012-12-26", "12:00", 22500, 20, 22500],
			[20, 500, "2012-12-26", "12:00", 10000, 15, 18000],
			[50, 1000, "2013-01-01", "12:00", 50000, 65, 68000],
			[5, 1000, "2013-01-01", "12:00", 5000, 20, 23000],
			["", 1000, "2012-12-26", "12:05", 15000, 10, 11500],
			[20, "", "2012-12-26", "12:05", 18000, 15, 18000],
			[10, 2000, "2012-12-26", "12:10", 20000, 5, 7600],
			[1, 1000, "2012-12-01", "00:00", 1000, 11, 12512.73],
			[0, "", "2012-12-26", "12:10", 0, -5, -5142.86]

		]

		for d in input_data:
			self.cleanup_data()
			self.insert_existing_sle("Moving Average")
			stock_reco = self.submit_stock_reconciliation(d[0], d[1], d[2], d[3])

			# check stock value in sle
			res = frappe.db.sql("""select stock_value from `tabStock Ledger Entry`
				where item_code = '_Test Item' and warehouse = '_Test Warehouse - _TC'
				and posting_date = %s and posting_time = %s order by name desc limit 1""",
				(d[2], d[3]))

			self.assertEqual(res and flt(res[0][0], 4) or 0, d[4])

			# bin qty and stock value
			bin = frappe.db.sql("""select actual_qty, stock_value from `tabBin`
				where item_code = '_Test Item' and warehouse = '_Test Warehouse - _TC'""")

			self.assertEqual(bin and [flt(bin[0][0]), flt(bin[0][1], 4)] or [],
				[flt(d[5]), flt(d[6])])

			# no gl entries
			gl_entries = frappe.db.sql("""select name from `tabGL Entry`
				where voucher_type = 'Stock Reconciliation' and voucher_no = %s""",
				stock_reco.name)
			self.assertFalse(gl_entries)

	def test_reco_fifo_gl_entries(self):
		frappe.defaults.set_global_default("auto_accounting_for_stock", 1)

		# [[qty, valuation_rate, posting_date, posting_time, stock_in_hand_debit]]
		input_data = [
			[50, 1000, "2012-12-26", "12:00"],
			[5, 1000, "2012-12-26", "12:00"],
			[15, 1000, "2012-12-26", "12:00"],
			[25, 900, "2012-12-26", "12:00"],
			[20, 500, "2012-12-26", "12:00"],
			["", 1000, "2012-12-26", "12:05"],
			[20, "", "2012-12-26", "12:05"],
			[10, 2000, "2012-12-26", "12:10"],
			[0, "", "2012-12-26", "12:10"],
			[50, 1000, "2013-01-01", "12:00"],
			[5, 1000, "2013-01-01", "12:00"],
			[1, 1000, "2012-12-01", "00:00"],
		]

		for d in input_data:
			self.cleanup_data()
			self.insert_existing_sle("FIFO")
			self.assertFalse(get_stock_and_account_difference(["_Test Account Stock In Hand - _TC"]))
			stock_reco = self.submit_stock_reconciliation(d[0], d[1], d[2], d[3])


			self.assertFalse(get_stock_and_account_difference(["_Test Account Stock In Hand - _TC"]))

			stock_reco.cancel()
			self.assertFalse(get_stock_and_account_difference(["_Test Account Stock In Hand - _TC"]))

		frappe.defaults.set_global_default("auto_accounting_for_stock", 0)

	def test_reco_moving_average_gl_entries(self):
		frappe.defaults.set_global_default("auto_accounting_for_stock", 1)

		# [[qty, valuation_rate, posting_date,
		#		posting_time, stock_in_hand_debit]]
		input_data = [
			[50, 1000, "2012-12-26", "12:00", 36500],
			[5, 1000, "2012-12-26", "12:00", -8500],
			[15, 1000, "2012-12-26", "12:00", 1500],
			[25, 900, "2012-12-26", "12:00", 9000],
			[20, 500, "2012-12-26", "12:00", -3500],
			["", 1000, "2012-12-26", "12:05", 1500],
			[20, "", "2012-12-26", "12:05", 4500],
			[10, 2000, "2012-12-26", "12:10", 6500],
			[0, "", "2012-12-26", "12:10", -13500],
			[50, 1000, "2013-01-01", "12:00", 50000],
			[5, 1000, "2013-01-01", "12:00", 5000],
			[1, 1000, "2012-12-01", "00:00", 1000],

		]

		for d in input_data:
			self.cleanup_data()
			self.insert_existing_sle("Moving Average")
			stock_reco = self.submit_stock_reconciliation(d[0], d[1], d[2], d[3])
			self.assertFalse(get_stock_and_account_difference(["_Test Warehouse - _TC"]))

			# cancel
			stock_reco.cancel()
			self.assertFalse(get_stock_and_account_difference(["_Test Warehouse - _TC"]))

		frappe.defaults.set_global_default("auto_accounting_for_stock", 0)


	def cleanup_data(self):
		frappe.db.sql("delete from `tabStock Ledger Entry`")
		frappe.db.sql("delete from tabBin")
		frappe.db.sql("delete from `tabGL Entry`")

	def submit_stock_reconciliation(self, qty, rate, posting_date, posting_time):
		stock_reco = frappe.get_doc({
			"doctype": "Stock Reconciliation",
			"posting_date": posting_date,
			"posting_time": posting_time,
			"fiscal_year": get_fiscal_year(posting_date)[0],
			"company": "_Test Company",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"reconciliation_json": json.dumps([
				["Item Code", "Warehouse", "Quantity", "Valuation Rate"],
				["_Test Item", "_Test Warehouse - _TC", qty, rate]
			]),
		})
		stock_reco.insert()
		stock_reco.submit()
		frappe.db.commit()
		return stock_reco

	def insert_existing_sle(self, valuation_method):
		frappe.db.set_value("Item", "_Test Item", "valuation_method", valuation_method)
		frappe.db.set_value("Stock Settings", None, "allow_negative_stock", 1)

		stock_entry = {
			"company": "_Test Company",
			"doctype": "Stock Entry",
			"posting_date": "2012-12-12",
			"posting_time": "01:00",
			"purpose": "Material Receipt",
			"fiscal_year": "_Test Fiscal Year 2012",
			"mtn_details": [
				{
					"conversion_factor": 1.0,
					"doctype": "Stock Entry Detail",
					"item_code": "_Test Item",
					"parentfield": "mtn_details",
					"incoming_rate": 1000,
					"qty": 20.0,
					"stock_uom": "_Test UOM",
					"transfer_qty": 20.0,
					"uom": "_Test UOM",
					"t_warehouse": "_Test Warehouse - _TC",
					"expense_account": "Stock Adjustment - _TC",
					"cost_center": "_Test Cost Center - _TC"
				}
			]
		}

		pr = frappe.copy_doc(stock_entry)
		pr.insert()
		pr.submit()

		pr1 = frappe.copy_doc(stock_entry)
		pr1.posting_date = "2012-12-15"
		pr1.posting_time = "02:00"
		pr1.get("mtn_details")[0].qty = 10
		pr1.get("mtn_details")[0].transfer_qty = 10
		pr1.get("mtn_details")[0].incoming_rate = 700
		pr1.insert()
		pr1.submit()

		pr2 = frappe.copy_doc(stock_entry)
		pr2.posting_date = "2012-12-25"
		pr2.posting_time = "03:00"
		pr2.purpose = "Material Issue"
		pr2.get("mtn_details")[0].s_warehouse = "_Test Warehouse - _TC"
		pr2.get("mtn_details")[0].t_warehouse = None
		pr2.get("mtn_details")[0].qty = 15
		pr2.get("mtn_details")[0].transfer_qty = 15
		pr2.get("mtn_details")[0].incoming_rate = 0
		pr2.insert()
		pr2.submit()

		pr3 = frappe.copy_doc(stock_entry)
		pr3.posting_date = "2012-12-31"
		pr3.posting_time = "08:00"
		pr3.purpose = "Material Issue"
		pr3.get("mtn_details")[0].s_warehouse = "_Test Warehouse - _TC"
		pr3.get("mtn_details")[0].t_warehouse = None
		pr3.get("mtn_details")[0].qty = 20
		pr3.get("mtn_details")[0].transfer_qty = 20
		pr3.get("mtn_details")[0].incoming_rate = 0
		pr3.insert()
		pr3.submit()


		pr4 = frappe.copy_doc(stock_entry)
		pr4.posting_date = "2013-01-05"
		pr4.fiscal_year = "_Test Fiscal Year 2013"
		pr4.posting_time = "07:00"
		pr4.get("mtn_details")[0].qty = 15
		pr4.get("mtn_details")[0].transfer_qty = 15
		pr4.get("mtn_details")[0].incoming_rate = 1200
		pr4.insert()
		pr4.submit()


test_dependencies = ["Item", "Warehouse"]
