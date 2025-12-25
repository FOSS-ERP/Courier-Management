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
        ]
    }
    
    create_custom_fields(custom_fields)        
    print("Custom Fields created successfully") 