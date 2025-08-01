import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_custom_fields():
    """Setup custom fields for Referral Practitioner Integration"""
    custom_fields = {
        "Shipment": [
            {
                "fieldname" : "courier_partner",
                "label" : "Courier Partner",
                "fieldtype" : "Link",
                "options" : "Courier Partner",
                "insert_after" : "shipment_delivery_note",
                "no_copy":1                
            },
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