import frappe
import requests
import json
from frappe.utils.data import get_url
from frappe.utils import flt


def validate(self, method):
    api_cred = get_api_credentials(self)
    validate_pincode(self, api_cred)
    generate_a_docket_no(self, api_cred)
    generate_a_parcel_series(self, api_cred)


def validate_pincode(self, api_cred=None):
    if not self.courier_partner:
        return
    
    if not api_cred:
        frappe.throw(frappe._("API credential is not updated"))

    delivery_pincode = get_delivery_pincode(self)
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

    try:
        response = requests.post(endpoint_url, timeout=10)
        response.raise_for_status()
        service_details = response.json()
        
        if service_details.get("docketNo"):
            self.awb_number = service_details.get("docketNo")
        else:
            frappe.throw("Failed to generate docket no.")

    except requests.exceptions.RequestException as e:
        frappe.log_error(f"API request failed: {e}", "DocketNO Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate Docket No"
            )
        )
    
def generate_a_parcel_series(self, api_cred):
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
        f"https://pg-uat.gati.com/pickupservices/Custpkgseries.jsp?p1={DOCKET_NO}&p2=2&p3={encode_customer_code}&p4={delivery_pincode}"
    )
    
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
        else:
            frappe.throw("Failed to package series no.")

    except requests.exceptions.RequestException as e:
        frappe.log_error(f"API request failed: {e}", "DocketNO Generation Error")
        frappe.throw(
            frappe._(
                "Failed to generate Docket No"
            )
        )

@frappe.whitelist()
def booking_of_shipment(doc):
    api_cred = get_api_credentials(doc)
    doc = frappe._dict(json.loads(doc))
    address_doc = frappe.get_doc("Address", doc.delivery_address_name)
    contact_doc = frappe.get_doc("Contact", doc.delivery_contact_name)

    customer_email_id = address_doc.email_id or contact_doc.address_doc.city or contact_doc.email_ids[0].email_id if contact_doc.email_ids else ''
    
    if not customer_email_id:
        frappe.throw("Receiver email id is not updated")

    customer_mobile_no = address_doc.phone or contact_doc.phone or contact_doc.mobile_no or contact_doc.phone_nos[0].phone if contact_doc.phone_nos else ''
    
    if not customer_mobile_no:
        frappe.throw("Receiver mobile no is not updated")
    
    payload = {
        "custCode": api_cred.customer_code,
        "details": [
            {
                "actualWt": doc.total_weight, 
                "bookingBasis": "2", 
                "chargedWt": 15, 
                "codAmt": "0", 
                "codInFavourOf": "G", 
                "consignorGSTINNo": "", 
                "CustDeliveyDate": "", 
                "custVendCode": frappe.db.get_value("Address", doc.pickup_address_name, "gstin"), 
                "declCargoVal": 23454.0,
                "deliveryStn": "", 
                "docketNo": doc.awb_number, 
                "EWAYBILL": doc.ewaybill_no, 
                "EWB_EXP_DT": "", 
                "fromPkgNo": doc.shipment_parcel[0].parcel_series, 
                "goodsCode": "302", 
                "goodsDesc": doc.description_of_content, 
                "instructions": "",
                "locationCode": "",
                "noOfPkgs": len(doc.shipment_parcel),
                "orderNo": doc.shipment_delivery_note[0].delivery_note, 
                "pkgDetails": {
                "pkginfo": [
                    {
                        "pkgBr": 1,
                        "pkgHt": 1,
                        "pkgLn": 2,
                        "pkgNo": 908895862, 
                        "pkgWt": 2, 
                        "custPkgNo":"" 
                    },
                    {
                        "pkgBr": 1,
                        "pkgHt": 1, 
                        "pkgLn": 2, 
                        "pkgNo":908895863, 
                        "pkgWt": 8, 
                        "custPkgNo":"" 
                    }
                ]
                },
                    "prodServCode": "1", 
                    "receiverAdd1": address_doc.address_title,
                    "receiverAdd2": address_doc.address_line1,
                    "receiverAdd3": address_doc.address_line2,
                    "receiverAdd4": address_doc.city,
                    "receiverCity": address_doc.state,
                    "receiverCode": "99999",
                    "receiverEmail": customer_email_id,
                    "ReceiverGSTINNo": address_doc.gstin,
                    "receiverMobileNo": customer_mobile_no,
                    "receiverName": frappe.db.get_value("Customer", doc.customer, "customer_name"),
                    "receiverPhoneNo": customer_mobile_no,
                    "receiverPinCode": address_doc.pincode,
                    "shipperCode": api_cred.customer_code, 
                    "toPkgNo": doc.shipment_parcel[-1].parcel_series, 
                    "UOM": "CC" 
                }
            ],
            "pickupRequest": "31-07-2025 10:23:57"
        }