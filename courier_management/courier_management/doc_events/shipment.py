import frappe
import requests
import json
from frappe.utils.data import get_url
from frappe.utils import flt, getdate, now_datetime, add_days, get_datetime, now
from datetime import datetime, time



def before_insert(self, method):
    set_default_pickup_time(self)

def validate(self, method):
    api_cred = get_api_credentials(self)
    validate_pickup_date(self)
    validate_pincode(self, api_cred)
    generate_a_docket_no(self, api_cred)
    generate_a_parcel_series(self, api_cred)

def validate_pickup_date(self):
    date_time = f"{self.pickup_date} {self.pickup_from}"
    pickup_time = get_datetime(date_time)
    if get_datetime(now()) > pickup_time:
        frappe.throw("Selected Pickup date and time should not be past.")


def on_submit(self, method):
    booking_of_shipment(self)
    docket_printing(self)

@frappe.whitelist()
def validate_pincode(doc, api_cred=None, api_call=False):
    if api_call:
        doc = frappe._dict(json.loads(doc))

    if not doc.courier_partner:
        return
        
    if not api_cred:
        api_cred = get_api_credentials(doc)

    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    delivery_pincode = get_delivery_pincode(doc)
    if not delivery_pincode:
        frappe.throw(frappe._("Delivery address is not selected or is missing a pincode."))

    token_code = api_cred.get_password("token_code")
    endpoint_url = get_url(
        f"https://pg-uat.gati.com/pickupservices/GKEPincodeserviceablity.jsp?reqid={token_code}&pincode={delivery_pincode}"
    )

    try:
        response = requests.post(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()
        
        if service_details.get("result") != "successful":
            frappe.throw(
                frappe._(f"Service is unavailable at pincode {frappe.bold(delivery_pincode)}")
            )
        
        return service_details
    except requests.exceptions.RequestException as e:
        frappe.log_error(f"API request failed: {e}", "Pincode Validation Error")
        frappe.throw(
            frappe._(
                f"Could not validate pincode {delivery_pincode} due to a connection error. Please try again later."
            )
        )

def get_delivery_pincode(self):
    if not self.delivery_address_name:
        return None
    return frappe.db.get_value("Address", self.delivery_address_name, "pincode")

def get_api_credentials(self):
    if not self.courier_partner:
        return
    
    api_cred = frappe.get_doc("Courier Partner", self.courier_partner)

    return api_cred

def generate_a_docket_no(self, api_cred=None):
    if not self.courier_partner:
        return
    if self.awb_number:
        return
    if not self.shipment_parcel:
        frappe.throw("Please Update a shipment parcel details")
    
    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    
    parcel_detail = [row for row in self.shipment_parcel if not row.parcel_series]

    endpoint_url = get_url(
        f"https://pg-uat.gati.com/pickupservices/GKEdktdownloadjson.jsp?p1={api_cred.get_password('encode_customer_code')}"
    )
    interaction_type = "Docket No"
    try:
        response = requests.post(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()
        
        if service_details.get("docketNo"):
            self.awb_number = service_details.get("docketNo")
        else:
            frappe.throw("Failed to generate docket no.")
        log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Completed")
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Failed")
        frappe.log_error(f"API request failed: {e}", "DocketNO Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate Docket No"
            )
        )
    
def generate_a_parcel_series(self, api_cred):
    if not self.courier_partner:
        return

    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    if not self.shipment_parcel:
        frappe.throw("Please Update a shipment parcel details")


    no_of_parcel = len([ row for row in self.shipment_parcel if not row.parcel_series ])
    if not no_of_parcel:
        return
    
    if not self.awb_number:
        frappe.throw(frappe._("Docket No is not Generated"))

    DOCKET_NO = self.awb_number
    encode_customer_code = api_cred.get_password("encode_customer_code")
    delivery_pincode = get_delivery_pincode(self)

    endpoint_url = get_url(
        f"https://pg-uat.gati.com/pickupservices/Custpkgseries.jsp?p1={DOCKET_NO}&p2={no_of_parcel}&p3={encode_customer_code}&p4={delivery_pincode}"
    )
    interaction_type = "Parcel Series"
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()

        if service_details.get("result") == "successful":
            self.awb_number = service_details.get("docketNo")
            
            from_no = int(service_details.get('frmNo'))
            to_no = int(service_details.get('toNo'))

            series = list(range(from_no, to_no + 1))

            i = 0
            for row in self.shipment_parcel:
                if not row.parcel_series:
                    row.parcel_series = series[i]
                    i+=1
            log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Completed")
        else:
            frappe.throw("Failed to package series no.")
            log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Failed")

    except requests.exceptions.RequestException as e:
        frappe.log_error(f"API request failed: {e}", "DocketNO Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate Docket No"
            )
        )

@frappe.whitelist()
def booking_of_shipment(doc):
    if not doc.courier_partner:
        return
    try:
        # 1. Input Validation and Data Preparation

        if isinstance(doc, str):
            doc = frappe._dict(json.loads(doc))

        api_cred = get_api_credentials(doc)
        if not api_cred:
            frappe.throw(frappe._("API credentials not found for this document."))

        # Fetch related documents
        try:
            address_doc = frappe.get_doc("Address", doc.delivery_address_name)
            contact_doc = frappe.get_doc("Contact", doc.delivery_contact_name)
        except Exception as e:
            frappe.throw(frappe._("Failed to fetch address or contact documents: {0}").format(e))

        # Get customer email and mobile, with robust fallbacks
        customer_email_id = (
            address_doc.email_id
            or (contact_doc.email_ids[0].email_id if contact_doc.email_ids else '')
        )
        if not customer_email_id:
            frappe.throw(frappe._("Receiver email id is not updated in the Address or Contact."))

        customer_mobile_no = (
            address_doc.phone
            or contact_doc.phone
            or contact_doc.mobile_no
            or (contact_doc.phone_nos[0].phone if contact_doc.phone_nos else '')
        )
        
        if not customer_mobile_no:
            frappe.throw(frappe._("Receiver mobile no is not updated in the Address or Contact."))

        # Get E-Waybill data
        delivery_note_name = doc.shipment_delivery_note[0].get('delivery_note')
        if not delivery_note_name:
            frappe.throw(frappe._("Delivery Note is not linked to the shipment."))

        ewaybill_data = get_ewaybill_no(delivery_note_name)

        # 2. Construct Payload
        payload = {
            "custCode": api_cred.customer_code,
            "details": [
                {
                    "actualWt": flt(doc.total_weight),
                    "bookingBasis": "2",  # Assuming this is a static value
                    "chargedWt": 15,  # This seems like a static value, maybe it should be dynamic?
                    "codAmt": "0",  # Assuming no COD for now
                    "codInFavourOf": "G",  # Assuming this is a static value
                    "consignorGSTINNo": frappe.db.get_value("Address", doc.pickup_address_name, "gstin") or '',
                    "CustDeliveyDate": "",  # Empty string as per original code
                    "custVendCode": "BLRS001", 
                    "declCargoVal": flt(doc.value_of_goods),
                    "deliveryStn": "",  # Empty string
                    "docketNo": doc.awb_number,
                    "EWAYBILL": ewaybill_data.get("ewaybill") or '',
                    "EWB_EXP_DT": '',
                    "fromPkgNo": doc.shipment_parcel[0].get("parcel_series"),
                    "goodsCode": "302",  
                    "goodsDesc": doc.description_of_content,
                    "instructions": "",
                    "locationCode": "",
                    "noOfPkgs": len(doc.shipment_parcel),
                    "orderNo": delivery_note_name,
                    "prodServCode": "1",  
                    "receiverAdd1": address_doc.address_title,
                    "receiverAdd2": address_doc.address_line1,
                    "receiverAdd3": address_doc.address_line2,
                    "receiverAdd4": address_doc.city,
                    "receiverCity": address_doc.state,
                    "receiverCode": "99999",  
                    "receiverEmail": customer_email_id,
                    "ReceiverGSTINNo": address_doc.gstin,
                    "receiverMobileNo": customer_mobile_no.replace(" ", '').replace("-", ""),
                    "receiverName": frappe.db.get_value("Customer", doc.delivery_customer, "customer_name"),
                    "receiverPhoneNo": customer_mobile_no.replace(" ", '').replace("-",""),
                    "receiverPinCode": address_doc.pincode,
                    "shipperCode": api_cred.customer_code,
                    "toPkgNo": doc.shipment_parcel[-1].get("parcel_series"),
                    "UOM": "CC"  
                }
            ],
            "pickupRequest": f"{(getdate(doc.pickup_date).strftime('%d-%m-%Y'))} {str(doc.pickup_from)[0:8]}" # Assuming pickup_from is a field in doc
        }


        pkginfo = []
        # Construct package details list
        for row in doc.shipment_parcel:
            if not (row.get("width")) or not row.get("height") or not row.get("length") or not row.get("weight"):
                frappe.throw(f"Row #{row.idx} : Height, Width, Length and Weight is required for parcel booking")
        
            pkginfo.append(
                {
                    "pkgBr": flt(row.get("width")),
                    "pkgHt": flt(row.get("height")),
                    "pkgLn": flt(row.get("length")),
                    "pkgNo": int(row.get("parcel_series")),
                    "pkgWt": flt(row.get("weight")),
                    "custPkgNo": ""
                }
            )

        payload["details"][0].update({"pkgDetails" : {"pkginfo": pkginfo}})

        # 3. API Call and Response Handling
        endpoint_url = get_url("https://pg-uat.gati.com/pickupservices/GATIKWEJPICKUPLBH.jsp")
        headers = {"Content-Type": "application/json"}

        # Use a more descriptive variable name than `url`
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        service_details = response.json()
        interaction_type = "Forword Pickup Booking"
        # Check for successful booking and update document
        if service_details.get("postedData") == 'successful':
            # The original code seems to have a typo, `postedData` is a string
            # and then it tries to get `postedData` from it again.
            # Assuming the response structure is something like:
            # {"status": "successful", "postedData": {"details": [...]}}
            # Let's adjust this logic to be more robust.
            if service_details.get("details"):
                for row in service_details["details"]:
                    frappe.db.set_value("Shipment", doc.name, "shipment_id", row.get("orderNo"))
            else:
                frappe.throw(frappe._("Booking successful but 'details' not found in response."))

            log_api_interaction(interaction_type, str(payload), service_details, status = "Completed")
            frappe.msgprint(frappe._("Successfully Booked"))
            return True
        else:
            # Handle API-specific error messages if available
            error_message = service_details.get("message") or service_details.get("error") or "Unknown error"
            log_api_interaction(interaction_type, str(payload), service_details, status = "Failed")
            frappe.throw(frappe._("Failed to book shipment: {0}").format(error_message))

    except requests.exceptions.RequestException as e:
        # Handle network or HTTP errors gracefully
        frappe.log_error(f"Gati API booking failed: {e}", "Gati API Error")
        frappe.throw(frappe._("Failed to connect to the Gati booking service. Please try again later."))
    except frappe.ValidationError:
        # Re-raise Frappe validation errors
        raise
    except Exception as e:
        # Catch any other unexpected errors
        frappe.log_error(f"An unexpected error occurred during shipment booking: {e}", "Shipment Booking Error")
        frappe.throw(frappe._("An unexpected error occurred. Please contact support."))


def get_ewaybill_no(delivery_note):
    si_data = frappe.db.sql(f"""
            Select si.name, si.ewaybill
            From `tabSales Invoice Item` as sii
            Left Join `tabSales Invoice` as si ON si.name = sii.name
            Where si.docstatus = 1 and sii.delivery_note = '{delivery_note}'
            Group By si.name
    """, as_dict=1)
    if si_data:
        ewaybill = si_data[0].get("ewaybill")

        validate_up_to = frappe.db.get_value(
            "e-Waybill Log", {
                "reference_name" : si_data[0].get("name"), 
                "is_cancelled":0
                },
                "valid_upto"
            )

        if ewaybill and validate_up_to:
            return { "ewaybill" : ewaybill, "valid_upto":validate_up_to }
        else:
            return {}
    else:
        dn_doc = frappe.get_doc("Delivery Note", delivery_note)
        si_reference = [ row.against_sales_invoice for row in dn_doc.items if row.against_sales_invoice ]
        frappe.throw(str(si_reference))
        if si_reference:
            ewaybill = frappe.db.get_value("Sales Invoice", si_reference[0], "ewaybill")

            validate_up_to = frappe.db.get_value(
                "e-Waybill Log", {
                    "reference_name" : si_reference[0], 
                    "is_cancelled":0
                    },
                    "valid_upto"
                )

            if ewaybill and validate_up_to:
                return { "ewaybill" : ewaybill, "valid_upto":validate_up_to }
            else:
                return {}


def log_api_interaction(interaction_type, request_data, response_data, status = None):
    """Log API requests and responses for auditing"""
    log = frappe.get_doc({
        "doctype": "Integration Request",
        "integration_type": "Remote",
        "integration_request_service": "Bank POS",
        "status": status,
        "request_description": interaction_type,
        "data": json.dumps(request_data),
        "output": json.dumps(response_data)
    })
    log.insert(ignore_permissions=True)
    frappe.db.commit()

@frappe.whitelist()
def docket_printing(doc):
    # 1. Input Validation and Data Preparation
  
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    if not doc.courier_partner:
        return

    api_cred = get_api_credentials(doc)

    if not doc.awb_number:
        frappe.throw(frappe._("Docket No is not generated"))

    endpoint_url = get_url(
        f"https://pg-uat.gati.com/InterfaceA4Print.jsp?p1={doc.awb_number}&p2={api_cred.customer_code}"
    )
    interaction_type = "Docket Printing"
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        pdf_content = response.content

        filename = "{0}-docket.pdf".format(doc.name)
        log_api_interaction(interaction_type, str(endpoint_url), str(response), status = "Completed")
        save_pdf_to_frappe(pdf_content, filename, doctype="Shipment", docname=doc.name)
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(response), status = "Failed")
        frappe.log_error(f"API request failed: {e}", "PDF Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate PDF"
            )
        )

    endpoint_url = f"https://pg-uat.gati.com/GATICOM_CUSTPKG.jsp?p1=3&p={doc.awb_number}&p3=3"
    label = "Label Print"
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        pdf_content = response.content

        filename = "{0}-label.pdf".format(doc.name)
        log_api_interaction(interaction_type, str(endpoint_url), str(response), status = "Completed")
        save_pdf_to_frappe(pdf_content, filename, doctype="Shipment", docname=doc.name)
        return True
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(response), status = "Failed")
        frappe.log_error(f"API request failed: {e}", "PDF Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate PDF"
            )
        )


def save_pdf_to_frappe(pdf_content, filename, doctype=None, docname=None, folder="Home"):
    try:
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "is_private": 1,  # Set to 1 if you want to restrict access
            "folder": folder
        })
        
        file_doc.content = pdf_content
        file_doc.save(ignore_permissions=True)  # Or file_doc.insert()
        
        frappe.db.commit() # Important to commit the changes
        frappe.msgprint(f"PDF '{filename}' saved successfully.")

    except Exception as e:
        frappe.log_error(f"Failed to save PDF to Frappe File: {e}", "File Save Error")
        frappe.db.rollback()
        return None

def set_default_pickup_time(doc):
    if not doc.courier_partner:
        return
    cutoff_time = time(16, 30)  # 4:30 PM
    pickup_start_time = time(16, 30)
    pickup_end_time = time(17, 30)

    current_time = now_datetime()
    current_time_only = current_time.time()

    # Decide pickup date
    if current_time_only < cutoff_time:
        pickup_date = current_time.date()
    else:
        pickup_date = add_days(current_time.date(), 1)

    # Assign values
    doc.pickup_date = pickup_date
    doc.pickup_from = pickup_start_time.strftime("%H:%M")
    doc.pickup_to = pickup_end_time.strftime("%H:%M")

@frappe.whitelist()
def cancelle_pickup_booking(doc):
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    if not doc.courier_partner:
        return

    api_cred = get_api_credentials(doc)

    payload = {
        "pickupRequest": f"{getdate(doc.pickup_date).strftime('%d-%m-%Y')} {doc.pickup_from}",
        "custCode": api_cred.customer_code,
            "details": [
                {
                    "docketNo": doc.awb_number,
                    "shipperCode": api_cred.customer_code,
                    "orderNo": doc.shipment_id,
                    "canReason": "Customer Order cancel"
                }
            ]
        }
    
    endpoint_url = get_url(
        "https://pg-uat.gati.com/pickupservices/b2bCanPickup.jsp"
    )

    interaction_type = "Cancelled Pickup Booking"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        response_json = response.json()

        if(response_json["postedData"] == 'successful'):
            if response_json['details']:
                frappe.msgprint(response_json['details'][0].get('errmsg'))
                frappe.db.set_value("Shipment", doc.name, "is_cancelled", 1)
                log_api_interaction(interaction_type, str(payload), response_json, status = "Completed")
            else:
                log_api_interaction(interaction_type, str(payload), response_json, status = "Failed")
                frappe.throw(frappe._("Details sections is not available in response"))
        else:
            log_api_interaction(interaction_type, str(payload), response_json, status = "Failed")
            frappe.throw(frappe._("Failed to cancelled booking"))

        return True
    except requests.exceptions.RequestException as e:
        frappe.log_error(f"API request failed: {e}", "Booking calcellation failed")
        frappe.throw(
            frappe._(
                "Failed to calcelled"
            )
        )

def before_cancel(self, method):
    if not self.courier_partner:
        return
    if not is_cancelled:
        frappe.throw("Shipment pickup service is not cancelled.")