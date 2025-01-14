# Copyright (c) 2021, Real Experts GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe import _, get_roles
from frappe.model.document import Document


class CatchLogEntry(Document):
	def before_insert(self):
		user_roles = set(get_roles(frappe.session.user))
		regional_origin = {
			"LANDA Regional Organization Management",
			"LANDA Regional Water Body Management",
			"LANDA State Organization Employee",
			"System Manager",
			"Administrator",
		}
		if regional_origin.intersection(user_roles):
			self.origin_of_catch_log_entry = "Regionalverband"
		else:
			self.origin_of_catch_log_entry = "Verein"

	def validate(self):
		# water_body = get_doc("Water Body", self.water_body)
		# main_species = [row.fish_species for row in water_body.fish_species]
		blacklisted_species = frappe.get_all(
			"Blacklisted Fish Species Table", {"parent": self.water_body}, pluck="fish_species"
		)

		for row in self.fish_catches:
			row.plausible = int(row.validate_weight())

			if blacklisted_species and (row.fish_species in blacklisted_species):
				frappe.throw(
					_("Row {0}: Fish Species {1} cannot occur in {2}").format(
						row.idx, frappe.bold(row.fish_species), frappe.bold(self.water_body_title)
					),
					title=_("Invalid Species"),
				)
