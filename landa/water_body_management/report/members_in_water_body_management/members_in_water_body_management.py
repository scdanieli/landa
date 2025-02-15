# Copyright (c) 2022, Real Experts GmbH and contributors
# For license information, please see license.txt

import frappe
import pandas as pd

from landa.utils import get_current_member_data

COLUMNS = [
	{
		"fieldname": "landa_member",
		"fieldtype": "Link",
		"options": "LANDA Member",
		"label": "Member",
	},
	{"fieldname": "first_name", "fieldtype": "Data", "label": "First Name"},
	{"fieldname": "last_name", "fieldtype": "Data", "label": "Last Name"},
	{
		"fieldname": "organization",
		"fieldtype": "Link",
		"options": "Organization",
		"label": "Organization",
	},
	{
		"fieldname": "organization_name",
		"fieldtype": "Data",
		"label": "Organization Name",
	},
	{
		"fieldname": "water_body",
		"fieldtype": "Link",
		"label": "Water Body",
		"options": "Water Body",
	},
	{
		"fieldname": "water_body_title",
		"fieldtype": "Data",
		"label": "Water Body Title",
	},
	{
		"fieldname": "primary_email_address",
		"fieldtype": "Data",
		"label": "Primary Email Address",
	},
	{
		"fieldname": "primary_phone",
		"fieldtype": "Data",
		"label": "Primary Phone",
	},
	{
		"fieldname": "primary_mobile",
		"fieldtype": "Data",
		"label": "Primary Mobile",
	},
	{
		"fieldname": "full_address",
		"fieldtype": "Data",
		"label": "Primary Address (Full)",
	},
	{
		"fieldname": "address_line1",
		"fieldtype": "Data",
		"label": "Address Line 1",
	},
	{"fieldname": "pincode", "fieldtype": "Data", "label": "Pincode"},
	{"fieldname": "city", "fieldtype": "Data", "label": "City"},
]


def get_data(filters=None):
	def remove_duplicate_indices(df, index="member", sort_by=None, keep="last"):
		"""Remove rows in dataframe with duplicate indeces.
		If sort_by is specified the dataframe is first sorted by these columns, keeping the entry specified in keep, e.g. 'last'"""
		if sort_by is not None:
			df = df.sort_values(sort_by)
		return df.reset_index().drop_duplicates(subset=[index], keep=keep).set_index(index)

	def get_link_filters(frappe_tuple, index="member"):
		member_ids = [m[index] for m in frappe_tuple]  # list of member names (ID)
		link_filters = [
			["Dynamic Link", "link_doctype", "=", "LANDA Member"],
			["Dynamic Link", "link_name", "in", member_ids],
		]
		return link_filters

	# load water body management from db
	wbm = frappe.get_all(
		"Water Body Management Local Organization",
		fields=[
			"water_body",
			"water_body_title",
			"fishing_area",
			"organization",
			"organization_name",
			"`tabWater Body Local Contact Table`.landa_member as member",
			"`tabWater Body Local Contact Table`.first_name",
			"`tabWater Body Local Contact Table`.last_name",
		],
		filters={"disabled": 0, **filters},
	)

	# convert to pandas dataframe
	wbm_df = pd.DataFrame.from_records(
		wbm,
		index="member",
		columns=[
			"water_body",
			"water_body_title",
			"fishing_area",
			"organization",
			"organization_name",
			"member",
			"first_name",
			"last_name",
		],
	)

	# define the labels of db entries that are supposed to be loaded
	link_field_label = "`tabDynamic Link`.link_name as member"
	link_filters = get_link_filters(wbm)

	# load addresses from db
	addresses = frappe.get_all(
		"Address",
		filters=link_filters,
		fields=[
			"address_line1",
			"pincode",
			"city",
			"is_primary_address",
			link_field_label,
		],
	)
	# convert to pandas dataframe
	addresses_df = pd.DataFrame.from_records(
		addresses,
		index="member",
		columns=["address_line1", "pincode", "city", "is_primary_address", "member"],
	)
	# remove all duplicate addresses by keeping only the primary address or last existing address if there is no primary address
	addresses_df = remove_duplicate_indices(addresses_df, sort_by="is_primary_address")

	# merge all columns to one address column and add this as the first column
	addresses_df["full_address"] = (
		addresses_df["address_line1"] + ", " + addresses_df["pincode"] + " " + addresses_df["city"]
	)
	address_cols = addresses_df.columns.tolist()
	addresses_df = addresses_df[address_cols[-1:] + address_cols[:-1]]
	# remove column 'is_primary_address'
	addresses_df.drop("is_primary_address", axis=1, inplace=True)

	# load contacts from db that are linked to the member fucntions loaded before
	contacts = frappe.get_all(
		"Contact",
		filters=link_filters,
		fields=["email_id", "phone", "mobile_no", link_field_label],
	)
	# convert to pandas dataframe
	contacts_df = pd.DataFrame.from_records(
		contacts, index="member", columns=["email_id", "phone", "mobile_no", "member"]
	)
	contacts_df = remove_duplicate_indices(contacts_df)

	# merge all dataframes from different doctypes and load data of all members without member functions only if necessary
	# sort columns as needed
	data = (
		pd.concat([wbm_df, contacts_df, addresses_df], axis=1)
		.reindex(
			[
				"first_name",
				"last_name",
				"organization",
				"organization_name",
				"water_body",
				"water_body_title",
				"email_id",
				"phone",
				"mobile_no",
				"full_address",
				"address_line1",
				"pincode",
				"city",
			],
			axis=1,
		)
		.fillna("")
		.reset_index()
	)

	return tuple(data.itertuples(index=False, name=None))


def execute(filters=None):
	regional_organization = get_current_member_data().regional_organization
	if regional_organization:
		filters["regional_organization"] = regional_organization

	return COLUMNS, get_data(filters)
