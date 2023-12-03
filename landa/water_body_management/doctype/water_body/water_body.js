// Copyright (c) 2021, Real Experts GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Water Body", {
	refresh: function (frm) {
		if (
			!frm.is_new() &&
			frappe.boot.landa.regional_organization &&
			frm.doc.organization !== frappe.boot.landa.regional_organization
		) {
			frm.disable_form();
		}

		frm.trigger("bind_rotation");
		frm.trigger("update_draw");

		frm.set_query(
			"icon",
			function (doc) {
				return {
					filters: {
						icon: ["is", "set"]
					},
				};
			}
		);
	},
	location: function (frm) {
		frm.trigger("update_draw");
	},
	icon: function (frm) {
		frm.trigger("bind_rotation");
	},
	icon_path: function (frm) {
		frm.trigger("update_draw");
		frm.refresh_field("icon_preview");

		// reset rotation
		frm.rotation_angle = 0;
		get_rotation_element().value = 0;
		frm.trigger("bind_rotation");
	},
	bind_rotation: function (frm) {
		if (!frm.doc.icon_path) {
			return;
		}

		bind_rotation_event(frm);
	},
	update_draw: function (frm) {
		update_draw_control(
			frm.fields_dict.location.draw_control,
			frm.doc.icon_path,
			frm.doc.icon,
			frm.rotation_angle,
		);
	},
});

function bind_rotation_event(frm) {
	const icon_rotation = get_rotation_element();
	const icon_preview = get_img_element(frm);
	icon_rotation.addEventListener("input", function (evt) {
		apply_rotation(icon_preview, evt.target.value);
		frm.rotation_angle = evt.target.value;
		frm.trigger("update_draw");
	});
}

function get_img_element(frm) {
	return frm.fields_dict.icon_preview.wrapper.getElementsByTagName("img")[0];
}

function get_rotation_element() {
	return document.getElementById("icon_rotation");
}

function apply_rotation(element, rotation_angle) {
	element.style.transform = `rotate(${rotation_angle}deg)`;
}

function update_draw_control(draw_control, icon_url, icon_name, rotation_angle) {
	if (!draw_control) {
		return;
	}
	let marker_config = {};

	if (icon_url) {
		const CustomIcon = L.Icon.extend({
			options: {
				iconSize: new L.Point(24, 24),
				iconUrl: icon_url,
				iconName: icon_name,
				rotationAngle: rotation_angle,
			},
		});
		marker_config.icon = new CustomIcon();
	}

	draw_control.setDrawingOptions({ marker: marker_config });
}

