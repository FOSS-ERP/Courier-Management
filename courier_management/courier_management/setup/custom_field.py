import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_custom_fields():
    """Setup custom fields for Referral Practitioner Integration"""
    custom_fields = {
        "Shipment": [
            {
                "fieldname" : "first_section_break",
                "label" : "Locations",
                "fieldtype" : "Section Break",
                "collapsible": 1
            },
            {
                "fieldname" : "locations",
                "label" : "",
                "fieldtype" : "HTML",
                "insert_after": "first_section_break"
            },
            {
                "fieldname" : "sec_section_break",
                "label" : "",
                "fieldtype" : "Section Break",
                "insert_after" : "locations",
                "collapsible": 1
            },
            {
                "fieldname" : "courier_partner",
                "label" : "Courier Partner",
                "fieldtype" : "Link",
                "options" : "Courier Partner",
                "insert_after" : "shipment_delivery_note",
                "no_copy":1                
            },
            {
                "fieldname" : "is_cancelled",
                "label" : "Is Pickup Booking Cancelled",
                "fieldtype" : "Check",
                "insert_after" : "courier_partner",
                "read_only":1 
            },
            {
                "fieldname" : "tracking_section_break",
                "label" : "Tracking",
                "fieldtype" : "Section Break",
                "collapsible": 1,
                "insert_after" : "locations"
            },
            {
                "fieldname" : "tracking_details",
                "label" : "",
                "fieldtype" : "HTML",
                "insert_after": "tracking_section_break"   
            },
            {
                "fieldname" : "invoice_value",
                "label" : "Invoice Value",
                "fieldtype" : "Currency",
                "insert_after" : "shipment_details_section",
                "depends_on" : "eval:doc.allow_new_invoice_values == 1;"
            },
            {
                "fieldname" : "invoice_no",
                "label" : "Invoice Number",
                "fieldtype" : "Data",
                "insert_after" : "column_break_36",
                "depends_on" : "eval:doc.allow_new_invoice_values == 1;"
            },
            {
                "fieldname" : "allow_new_invoice_values",
                "label" : "Allow New Invoice Value",
                "fieldtype" : "Check",
                "insert_after" : "delivery_customer",
                "fetch_from" : "delivery_customer.special_pricing_applicable_for_shipment"
            }
        ],
        "Shipment Parcel": [
            {
                "fieldname" : "parcel_series",
                "label" : "Parcel Details",
                "fieldtype" : "Data",
                "read_only" : 1,
                "insert_after" : "count",
                "no_copy":1  
            }
        ],
        "Customer" : [
            {
                "fieldname" : "special_pricing_applicable_for_shipment",
                "label" : "Special Pricing Applicable for Shipment",
                "fieldtype" : "Check",
                "read_only" : 0,
                "insert_after" : "dn_required",
                "no_copy":1  
            }
        ]
    }
    
    create_custom_fields(custom_fields)        
    print("Custom Fields created successfully") 