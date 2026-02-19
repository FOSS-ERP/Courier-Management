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

def validate_pickup_date(self):
    date_time = f"{self.pickup_date} {self.pickup_from}"
    pickup_time = get_datetime(date_time)
    if get_datetime(now()) > pickup_time:
        frappe.throw("Selected Pickup date and time should not be past.")

@frappe.whitelist()
def book_shipment(doc):
    import time
    doc = frappe._dict(json.loads(doc))
    api_cred = get_api_credentials(doc)
    validate_pincode(doc, api_cred)
    time.sleep(2)
    DocketNO = generate_a_docket_no(doc, api_cred)
    time.sleep(2)
    generate_a_parcel_series(doc, api_cred, DocketNO)
    time.sleep(2)
    booking_of_shipment(doc)
    time.sleep(2)
    docket_printing(doc)

    return "Booked Successfully"


@frappe.whitelist()
def validate_pincode(doc, api_cred=None, api_call=False):
    if api_call:
        doc = frappe._dict(json.loads(doc))

    if not doc.courier_partner:
        return
        
    if not api_cred:
        api_cred = get_api_credentials(doc)

    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url")
    else :
        base_url = api_cred.get("uat_base_url")

    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    delivery_pincode = get_delivery_pincode(doc)
    if not delivery_pincode:
        frappe.throw(frappe._("Delivery address is not selected or is missing a pincode."))

    token_code = api_cred.get_password("token_code")
    endpoint_url = get_url(
        f"https://{base_url}/webservices/GKEPincodeserviceability.jsp?reqid={token_code}&pincode={delivery_pincode}"
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
        frappe.log_error(title="Pincode Validation Error", message=str(e))
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

def generate_a_docket_no(doc, api_cred=None):
    if not doc.courier_partner:
        return
    
    if doc.awb_number:
        return doc.awb_number
    
    if not doc.shipment_parcel:
        frappe.throw("Please Update a shipment parcel details")
    
    if not api_cred:
        api_cred = get_api_credentials(doc)

    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url")
    else :
        base_url = api_cred.get("uat_base_url")

    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    
    parcel_detail = [row for row in doc.get("shipment_parcel") if not row.get("parcel_series")]

    endpoint_url = get_url( 
        f"https://{base_url}/webservices/GKEdktdownloadjson.jsp?p1={api_cred.get_password('encode_customer_code')}"
    )
    interaction_type = "Docket No"
    service_details = None
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()

        docket_no = service_details.get("docketNo")
        if docket_no and docket_no != "No Dockets To Download":
            frappe.db.set_value("Shipment", doc.name, "awb_number", docket_no)
            log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status="Completed")
            return docket_no
        errmsg = service_details.get("errmsg") or (
            "No dockets available for download. Please contact Gati SPOC for allocation."
            if docket_no == "No Dockets To Download" else "Failed to generate docket no."
        )
        log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status="Failed")
        frappe.throw(frappe._(errmsg))
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(service_details or str(e)), status="Failed")
        frappe.log_error(title="Docket Generation Error", message=str(e))
        frappe.throw(frappe._("Failed to generate Docket No"))
    
def generate_a_parcel_series(doc, api_cred, DocketNO):
    if not doc.courier_partner:
        return

    if not api_cred:
        api_cred = get_api_credentials(doc)

    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url")
    else :
        base_url = api_cred.get("uat_base_url")

    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    if not doc.shipment_parcel:
        frappe.throw("Please Update a shipment parcel details")


    no_of_parcel = len([ row for row in doc.shipment_parcel if not row.get("parcel_series") ])
    if not no_of_parcel:
        return
    
    if not DocketNO:
        frappe.throw(frappe._("Docket No is not Generated"))

    DOCKET_NO = DocketNO
    encode_customer_code = api_cred.get_password("encode_customer_code")
    delivery_pincode = get_delivery_pincode(doc)

    endpoint_url = get_url(
        f"https://{base_url}/webservices/Custpkgseries.jsp?p1={DOCKET_NO}&p2={no_of_parcel}&p3={encode_customer_code}&p4={delivery_pincode}"
    )
    interaction_type = "Parcel Series"
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()

        if service_details.get("result") == "successful":
            doc.awb_number = service_details.get("docketNo")
            
            from_no = int(service_details.get('frmNo'))
            to_no = int(service_details.get('toNo'))

            series = list(range(from_no, to_no + 1))

            i = 0
            for row in doc.shipment_parcel:
                if not row.get("parcel_series"):
                    frappe.db.set_value(row.get("doctype"), row.get("name"), "parcel_series", series[i])
                    i+=1
            log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Completed")
        else:
            log_api_interaction(interaction_type, str(endpoint_url), str(service_details), status = "Failed")
            frappe.throw("Failed to package series no.")

    except requests.exceptions.RequestException as e:
        frappe.log_error(title="Parcel Series Error", message=str(e))
        frappe.throw(frappe._("Failed to generate Docket No"))

@frappe.whitelist()
def booking_of_shipment(doc):
    doc = frappe.get_doc(doc.get("doctype"), doc.get("name"))

    if not doc.courier_partner:
        return
    try:
        # 1. Input Validation and Data Preparation

        if isinstance(doc, str):
            doc = frappe._dict(json.loads(doc))

        api_cred = get_api_credentials(doc)

        if api_cred.enable_production_mode:
            base_url = api_cred.get("prod_base_url")
        else :
            base_url = api_cred.get("uat_base_url")

        if not api_cred:
            frappe.throw(frappe._("API credentials not found for this document."))

        # Fetch related documents
        try:
            address_doc = frappe.get_doc("Address", doc.delivery_address_name)
        except Exception as e:
            frappe.throw(frappe._("Failed to fetch delivery address: {0}").format(e))

        # Get customer email and mobile, with robust fallbacks (address first, then contact)
        def _digits_only(s):
            return "".join(c for c in (s or "") if c.isdigit())

        customer_email_id = address_doc.email_id or ""
        customer_mobile_no = _digits_only(address_doc.phone or getattr(address_doc, "mobile_no", None) or "")

        if doc.delivery_contact_name:
            try:
                contact_doc = frappe.get_doc("Contact", doc.delivery_contact_name)
                if not customer_email_id and contact_doc.email_ids:
                    customer_email_id = contact_doc.email_ids[0].email_id or ""
                if not customer_mobile_no:
                    customer_mobile_no = _digits_only(
                        contact_doc.phone or contact_doc.mobile_no or ""
                    )
                if not customer_mobile_no and contact_doc.phone_nos:
                    customer_mobile_no = _digits_only(contact_doc.phone_nos[0].phone or "")
            except Exception:
                pass

        # Indian mobile: use last 10 digits (handles +91 prefix)
        if len(customer_mobile_no) > 10:
            customer_mobile_no = customer_mobile_no[-10:]

        if not customer_email_id:
            frappe.throw(frappe._("Receiver email id is not updated in the Address or Contact."))

        if not customer_mobile_no or len(customer_mobile_no) < 10:
            frappe.throw(frappe._("Receiver mobile no (min 10 digits) is not updated in the Address or Contact."))

        # Get E-Waybill data
        delivery_note_name = doc.shipment_delivery_note[0].get('delivery_note')
        if not delivery_note_name:
            frappe.throw(frappe._("Delivery Note is not linked to the shipment."))

        ewaybill_data = get_ewaybill_no(doc)
        order_no = ewaybill_data.get("sales_invoice") or delivery_note_name
        # 2. Construct Payload

        if doc.ewaybill_no:
            ewaybill_no = doc.ewaybill_no
        else:
            if ewaybill_data and ewaybill_data.get("ewaybill"):
                ewaybill_no = ewaybill_data.get("ewaybill")
            else:
                ewaybill_no = ''
            
        if doc.ewaybill_date:
            ewaybill_date = str(getdate(doc.ewaybill_date).strftime('%d-%m-%Y'))
        else:
            if ewaybill_data and ewaybill_data.get("valid_upto"):
                ewaybill_date = str(getdate(ewaybill_data.get("valid_upto")).strftime('%d-%m-%Y'))
            else:
                ewaybill_date = ''

        # Charged weight: use actual total weight (Gati may apply volumetric rules server-side)
        charged_wt = max(flt(doc.total_weight), 1)

        payload = {
            "custCode": api_cred.customer_code,
            "details": [
                {
                    "actualWt": flt(doc.total_weight),
                    "bookingBasis": "2",
                    "chargedWt": charged_wt,
                    "codAmt": "0",
                    "codInFavourOf": "G",
                    "consignorGSTINNo": frappe.db.get_value("Address", doc.pickup_address_name, "gstin") or '',
                    "CustDeliveyDate": "",
                    "custVendCode": "BLRS001",
                    "declCargoVal": flt(doc.invoice_value) or flt(doc.value_of_goods),
                    "deliveryStn": "",
                    "docketNo": doc.awb_number,
                    "EWAYBILL": ewaybill_no,
                    "EWB_EXP_DT": ewaybill_date,
                    "fromPkgNo": doc.shipment_parcel[0].get("parcel_series"),
                    "goodsCode": "302",
                    "goodsDesc": doc.description_of_content or "as per invoice",
                    "instructions": "",
                    "locationCode": "",
                    "noOfPkgs": len(doc.shipment_parcel),
                    "orderNo": doc.invoice_no or order_no,
                    "prodServCode": "1",
                    "receiverAdd1": (address_doc.address_title or "")[:50],
                    "receiverAdd2": (address_doc.address_line1 or "")[:50],
                    "receiverAdd3": (address_doc.address_line2 or "")[:50],
                    "receiverAdd4": (address_doc.city or "")[:50],
                    "receiverCity": (address_doc.state or "")[:20],
                    "receiverCode": "99999",
                    "receiverEmail": (customer_email_id.split(',')[0] or "").strip()[:50],
                    "ReceiverGSTINNo": address_doc.gstin or '',
                    "receiverMobileNo": customer_mobile_no[:10],
                    "receiverName": (frappe.db.get_value("Customer", doc.delivery_customer, "customer_name") or "")[:50],
                    "receiverPhoneNo": customer_mobile_no[:10],
                    "receiverPinCode": str(address_doc.pincode or "")[:6],
                    "shipperCode": api_cred.customer_code,
                    "toPkgNo": doc.shipment_parcel[-1].get("parcel_series"),
                    "UOM": "CC"
                }
            ],
            "pickupRequest": f"{(getdate(doc.pickup_date).strftime('%d-%m-%Y'))} {str(doc.pickup_from or '')[:8]}"
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
        endpoint_url = get_url(f"https://{base_url}/webservices/GATIKWEJPICKUPLBH.jsp")
        headers = {"Content-Type": "application/json"}
        interaction_type = "Forword Pickup Booking"
        log_api_interaction(interaction_type, str(payload), "Before Trigger the API", status = "Completed")
        # Use a more descriptive variable name than `url`
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        try:
            service_details = response.json()
        except ValueError:
            frappe.log_error(title="Gati Booking Response Error", message=f"Invalid JSON. Raw: {response.text[:500]}")
            frappe.throw(frappe._("Invalid response from Gati API. Check Error Log for details."))

        # Check for successful booking and update document
        if service_details.get("postedData") == 'successful':
            if service_details.get("details"):
                for row in service_details["details"]:
                    if row.get("orderNo"):
                        frappe.db.set_value("Shipment", doc.name, "shipment_id", row.get("orderNo"))
                        break
            log_api_interaction(interaction_type, str(payload), service_details, status="Completed")
            frappe.msgprint(frappe._("Successfully Booked"))
            return True

        # Extract error message from Gati API response
        error_message = "Unknown error"
        if service_details.get("details") and len(service_details["details"]) > 0:
            first_detail = service_details["details"][0]
            error_message = first_detail.get("errmsg") or error_message
        error_message = (
            service_details.get("errmsg")
            or service_details.get("message")
            or service_details.get("error")
            or error_message
        )
        log_api_interaction(interaction_type, str(payload), service_details, status="Failed")
        frappe.throw(frappe._("Failed to book shipment: {0}").format(error_message))

    except requests.exceptions.RequestException as e:
        # Handle network or HTTP errors gracefully
        frappe.log_error(title="Gati API Error", message=str(e))
        frappe.throw(frappe._("Failed to connect to the Gati booking service. Please try again later."))
    except frappe.ValidationError:
        # Re-raise Frappe validation errors
        raise
    except Exception as e:
        # Catch any other unexpected errors
        frappe.log_error(title="Shipment Booking Error", message=str(e))
        frappe.throw(frappe._("An unexpected error occurred. Please contact support."))


from frappe.utils import getdate

MAX_INVOICE_ALLOWED = 3


def get_ewaybill_no(doc):
    sales_invoices = set()

    # ---------------------------------------------------
    # 1️⃣ DN → Sales Invoice (DN created from Invoice)
    # ---------------------------------------------------
    for dn in get_unique_dns(doc):
        si_data = frappe.db.sql("""
            SELECT DISTINCT si.name
            FROM `tabSales Invoice Item` sii
            JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
              AND sii.delivery_note = %s
        """, dn, as_dict=True)

        sales_invoices.update(d.name for d in si_data)

    # ---------------------------------------------------
    # 2️⃣ DN → against_sales_invoice (Invoice → DN link)
    # ---------------------------------------------------
    for dn in get_unique_dns(doc):
        dn_doc = frappe.get_doc("Delivery Note", dn)
        sales_invoices.update(
            row.against_sales_invoice
            for row in dn_doc.items
            if row.against_sales_invoice
        )

    # ---------------------------------------------------
    # 3️⃣ DN → SO → Sales Invoice
    #    (covers your exact scenario)
    # ---------------------------------------------------
    for dn in get_unique_dns(doc):
        dn_doc = frappe.get_doc("Delivery Note", dn)

        sales_orders = [
            row.against_sales_order
            for row in dn_doc.items
            if row.against_sales_order
        ]

        if not sales_orders:
            continue

        si_data = frappe.db.sql("""
            SELECT DISTINCT parent
            FROM `tabSales Invoice Item`
            WHERE parenttype = 'Sales Invoice'
              AND sales_order IN %s
        """, (tuple(sales_orders),), as_dict=True)

        sales_invoices.update(d.parent for d in si_data)

    # ---------------------------------------------------
    # 🚫 No invoice found
    # ---------------------------------------------------
    if not sales_invoices:
        frappe.log_error("Sales Invoice Not Found", "Courier Integration")
        return {}

    # ---------------------------------------------------
    # 🚨 Validate invoice count (DEDUPED)
    # ---------------------------------------------------
    if len(sales_invoices) > MAX_INVOICE_ALLOWED:
        frappe.throw("No of Invoices more than three is not allowed")

    return build_invoice_response(sales_invoices)


# ================= HELPERS ================= #

def build_invoice_response(sales_invoices):
    invoice_display = []
    ewaybill_list = []

    for si in sales_invoices:
        invoice_display.append(si.split("/")[-1])

        ewaybill = frappe.db.get_value("Sales Invoice", si, "ewaybill")
        if ewaybill:
            ewaybill_list.append(ewaybill)

    response = {
        "sales_invoice": "X".join(sorted(invoice_display))
    }

    if ewaybill_list:
        response["ewaybill"] = ",".join(sorted(set(ewaybill_list)))
        response["valid_upto"] = getdate(
            frappe.db.get_value(
                "e-Waybill Log",
                ewaybill_list[0],
                "valid_upto"
            )
        )

    return response


def get_unique_dns(doc):
    return {row.delivery_note for row in doc.shipment_delivery_note}

                


def log_api_interaction(interaction_type, request_data, response_data, status = None):
    """Log API requests and responses for auditing"""
    log = frappe.get_doc({
        "doctype": "Integration Request",
        "integration_type": "Remote",
        "integration_request_service": "Courier Booking",
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
    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url_sticker")
    else :
        base_url = api_cred.get("uat_base_url_sticker")

    if not doc.awb_number:
        frappe.throw(frappe._("Docket No is not generated"))

    endpoint_url = get_url(
        f"https://{base_url}/Greport/InterfaceA4Print.jsp?p1={doc.awb_number}&p2={api_cred.customer_code}"
    )
    interaction_type = "Docket Printing"
    try:
        import time
        time.sleep(3)
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        pdf_content = response.content
        filename = "{0}-docket.pdf".format(doc.name)
        log_api_interaction(interaction_type, str(endpoint_url), f"Status: {response.status_code}", status="Completed")
        save_pdf_to_frappe(pdf_content, filename, doctype="Shipment", docname=doc.name)
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(e), status="Failed")
        frappe.log_error(title="PDF Generation Error", message=str(e))
        frappe.throw(
            frappe._(
                "Failed to generate PDF"
            )
        )

    endpoint_url = get_url(f"https://{base_url}/Greport/GATICOM_CUSTPKG.jsp?p1=3&p={doc.awb_number}&p3=3")
    label = "Label Print"
    try:
        response = requests.get(endpoint_url, timeout=10)
        response.raise_for_status()
        pdf_content = response.content

        filename = "{0}-label.pdf".format(doc.name)
        log_api_interaction(interaction_type, str(endpoint_url), f"Status: {response.status_code}", status="Completed")
        save_pdf_to_frappe(pdf_content, filename, doctype="Shipment", docname=doc.name)
        return True
    except requests.exceptions.RequestException as e:
        log_api_interaction(interaction_type, str(endpoint_url), str(e), status="Failed")
        frappe.log_error(title="PDF Generation Error", message=str(e))
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
        frappe.log_error(title="File Save Error", message=str(e))
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
    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url")
    else :
        base_url = api_cred.get("uat_base_url")

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
        f"https://{base_url}/webservices/b2bCanPickup.jsp"
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
        frappe.log_error(title="Booking Cancellation Error", message=str(e))
        frappe.throw(
            frappe._(
                "Failed to calcelled"
            )
        )

def before_cancel(self, method):
    if not self.courier_partner:
        return
    if not (self.shipment_id or self.awb_number):
        return
    if not self.is_cancelled:
        frappe.throw("Shipment pickup service is not cancelled.")


## track gati function
@frappe.whitelist()
def track_gati_awb(doc, api_cred=None, api_call=False):
    if api_call:
        doc = frappe._dict(json.loads(doc))
    if not doc.courier_partner:
        return
    if doc.is_cancelled:
        return
    if not api_cred:
        api_cred = get_api_credentials(doc)
    if not api_cred:
        frappe.throw(frappe._("API credentials is not updated"))

    if api_cred.enable_production_mode:
        base_url = api_cred.get("prod_base_url")
    else :
        base_url = api_cred.get("uat_base_url")
    token_code = api_cred.get_password("token_code")

    if not token_code:
        frappe.throw(frappe._("GATI security token is missing"))
    ## api url
    endpoint_url = get_url(
        f"https://{base_url}/webservices/GatiKWEDktJTrack.jsp?p1={doc.awb_number}&p2={token_code}"
    )
    
    try:
        response = requests.get(endpoint_url, timeout=15)
        response.raise_for_status()
        tracking_details = response.json()
        interaction_type = "Completed"
        request_data = endpoint_url
        response_data = tracking_details
        log_api_interaction(interaction_type, request_data, response_data, status = None)
        gati_response = tracking_details.get("Gatiresponse", {})
        dktinfo = gati_response.get("dktinfo", [])

        if not dktinfo:
            frappe.throw(frappe._("Invalid response received from GATI"))

        docket = dktinfo[0]

        # api-level error handling
        if docket.get("errmsg"):
            frappe.throw(frappe._(docket.get("errmsg")))
        return tracking_details
        
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            message = f"API request failed: {e}",
            title= "GATI Tracking API Error"
        )
        frappe.throw(
            frappe._(
                "Could not fetch tracking details from GATI due to a connection error."
                "Please try again later."
            )
        )


@frappe.whitelist()
def get_delevery_note_details(delivery_note):
    return frappe.db.sql(f"""
                            Select parent as delivery_note, amount
                            From `tabDelivery Note Item` as dni
                            where parent = '{delivery_note}'
                         """, as_dict=1)