# Copyright (c) 2022, Real Experts GmbH and contributors
# For license information, please see license.txt

from typing import List

import frappe
from frappe import _
from pypika.functions import Coalesce, Substring, Sum
from pypika.queries import Table
from pypika.terms import Criterion

from landa.organization_management.doctype.organization.organization import (
	get_supported_water_bodies,
)
from landa.utils import get_current_member_data

STATE_ROLES = {"LANDA State Organization Employee", "System Manager", "Administrator"}
REGIONAL_ROLES = {
	"LANDA Regional Organization Management",
	"LANDA Regional Water Body Management",
}

COLUMNS = [
	{
		"fieldname": "water_body",
		"fieldtype": "Link",
		"label": "Water Body",
		"options": "Water Body",
	},
	{
		"fieldname": "fish_species",
		"fieldtype": "Link",
		"label": "Fish Species",
		"options": "Fish Species",
	},
	{
		"fieldname": "amount",
		"fieldtype": "Int",
		"label": "Number of Fish",
	},
	{
		"fieldname": "weight_in_kg",
		"fieldtype": "Float",
		"label": "Weight in Kg",
	},
	{  # displayed only for regional or state employees
		"fieldname": "by_foreign_regional_org",
		"fieldtype": "Percent",
		"label": "Share of other Regional Organizations",
	},
]


def get_columns():
	columns = COLUMNS.copy()
	if not is_regional_or_state_employee():
		columns.pop()

	return columns


def get_data(filters):
	entry = frappe.qb.DocType("Catch Log Entry")
	child_table = frappe.qb.DocType("Catch Log Fish Table")
	qb_filters = get_qb_filters(filters, entry, child_table)

	by_all_regional_orgs = get_subquery(entry, child_table, qb_filters)
	by_foreign_regional_orgs = get_subquery(
		entry,
		child_table,
		qb_filters
		+ [Substring(entry.organization, 1, 3) != entry.regional_organization],  # index starts at 1
	)

	proportion_foreign = (
		frappe.qb.from_(by_all_regional_orgs)
		.left_join(by_foreign_regional_orgs)
		.on(
			(by_all_regional_orgs.water_body == by_foreign_regional_orgs.water_body)
			& (by_all_regional_orgs.fish_species == by_foreign_regional_orgs.fish_species)
		)
		.select(
			by_all_regional_orgs.water_body,
			by_all_regional_orgs.fish_species,
			(
				Coalesce(by_foreign_regional_orgs.total_weight_in_kg, 0)
				/ by_all_regional_orgs.total_weight_in_kg
				* 100
			).as_("by_foreign_regional_org"),
		)
	)

	query = (
		frappe.qb.from_(entry)
		.join(child_table)
		.on(entry.name == child_table.parent)
		.left_join(proportion_foreign)
		.on(
			(entry.water_body == proportion_foreign.water_body)
			& (child_table.fish_species == proportion_foreign.fish_species)
		)
		.select(
			entry.water_body,
			child_table.fish_species,
			Sum(child_table.amount),
			Sum(child_table.weight_in_kg),
		)
	)

	if is_regional_or_state_employee():
		query = query.select(proportion_foreign.by_foreign_regional_org)

	query = filter_and_group(query, entry, child_table, qb_filters)
	return query.run()


def get_subquery(entry: Table, child_table: Table, qb_filters: List[Criterion]):
	subquery = (
		frappe.qb.from_(entry)
		.join(child_table)
		.on(entry.name == child_table.parent)
		.select(
			entry.water_body,
			child_table.fish_species,
			Sum(child_table.weight_in_kg).as_("total_weight_in_kg"),
		)
	)

	return filter_and_group(subquery, entry, child_table, qb_filters)


def filter_and_group(query, entry: Table, child_table: Table, qb_filters: List[Criterion]):
	query = add_conditions(query, qb_filters)
	query = add_or_filters(query, entry)
	query = query.groupby(entry.water_body, child_table.fish_species)
	return query


def get_qb_filters(filters, entry, child_table):
	filters["workflow_state"] = "Approved"
	fish_species = filters.pop("fish_species", None)
	from_year = filters.pop("from_year", None)
	to_year = filters.pop("to_year", None)

	qb_filters = [entry[key] == value for key, value in filters.items()]

	if fish_species:
		qb_filters.append(child_table.fish_species == fish_species)

	if from_year:
		qb_filters.append(entry.year >= from_year)

	if to_year:
		qb_filters.append(entry.year <= to_year)

	return qb_filters


def add_or_filters(query, entry):
	"""Return a dict of filters that restricts the results to what the user is
	allowed to see.

	STATE_ROLES		no filters
	REGIONAL_ROLES	everything related to their water bodys OR to their member organizations
	LOCAL_ROLES		everything related to their own organization and OR to the water bodys it is supporting
	"""
	user_roles = get_user_roles()

	if user_roles.intersection(STATE_ROLES):
		return query

	# User is not a state organization employee

	member_data = get_current_member_data()
	if not member_data:
		frappe.throw(_("You are not a member of any organization."))

	if user_roles.intersection(REGIONAL_ROLES):
		return query.where(
			(entry.regional_organization == member_data.regional_organization)
			| entry.organization.like(f"{member_data.regional_organization}-%")
		)

	# User is not in regional organization management
	supported_water_bodies = get_supported_water_bodies(member_data.local_organization)
	if supported_water_bodies:
		return query.where(
			entry.organization.like(f"{member_data.local_organization}%")
			| entry.water_body.isin(supported_water_bodies)
		)

	return query.where(entry.organization.like(f"{member_data.local_organization}%"))


def add_conditions(query, conditions):
	for condition in conditions:
		query = query.where(condition)

	return query


def get_user_roles():
	return set(frappe.get_roles())


def is_regional_or_state_employee():
	user_roles = get_user_roles()
	return REGIONAL_ROLES.intersection(user_roles) or STATE_ROLES.intersection(user_roles)


def execute(filters=None):
	return get_columns(), get_data(filters) or []
