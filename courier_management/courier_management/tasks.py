import frappe
from courier_management.courier_management.doc_events.shipment import track_gati_awb

NOTIFICATION_OUT_FROM_ORIGIN = "shipment email 1"
NOTIFICATION_DELIVERED = "shipment email 2"


def hourly():
    track_shipment_status()


def track_shipment_status():
    """Hourly scheduler: poll Gati tracking API and send status emails.

    Sends one email when status becomes "Out From Origin" and one when "Delivered".
    Each email is sent only once per shipment.
    """
    shipments = frappe.get_all(
        "Shipment",
        filters={
            "awb_number": ["!=", ""],
            "courier_partner": ["!=", ""],
            "is_cancelled": 0,
            "docstatus": 1,
        },
        or_filters=[
            ["out_from_origin_email_sent", "=", 0],
            ["delivered_email_sent", "=", 0],
        ],
        fields=[
            "name",
            "awb_number",
            "courier_partner",
            "out_from_origin_email_sent",
            "delivered_email_sent",
        ],
    )

    for row in shipments:
        try:
            _process_shipment_tracking(row.name)
        except Exception:
            frappe.log_error(
                title="Shipment Tracking Scheduler Error",
                message=frappe.get_traceback(),
            )


def _process_shipment_tracking(shipment_name):
    doc = frappe.get_doc("Shipment", shipment_name)

    # Skip if both emails already sent
    if doc.out_from_origin_email_sent and doc.delivered_email_sent:
        return

    tracking = track_gati_awb(doc)
    if not tracking:
        return

    gati_response = tracking.get("Gatiresponse", {})
    dktinfo = gati_response.get("dktinfo", [])
    if not dktinfo:
        return

    status = dktinfo[0].get("DOCKET_STATUS", "")

    if status == "Out From Origin" and not doc.out_from_origin_email_sent:
        _trigger_notification(doc, NOTIFICATION_OUT_FROM_ORIGIN)
        frappe.db.set_value("Shipment", doc.name, {
            "out_from_origin_email_sent": 1,
            "delivery_status": "Out From Origin",
        })

    if status == "Delivered" and not doc.delivered_email_sent:
        _trigger_notification(doc, NOTIFICATION_DELIVERED)
        frappe.db.set_value("Shipment", doc.name, {
            "delivered_email_sent": 1,
            "delivery_status": "Delivered",
        })


def _trigger_notification(doc, notification_name):
    """Send a Frappe Notification by name against the given Shipment doc."""
    if not frappe.db.exists("Notification", notification_name):
        frappe.log_error(
            title="Shipment Tracking – Notification Not Found",
            message=f"Notification '{notification_name}' does not exist. Skipping for Shipment {doc.name}.",
        )
        return

    notification = frappe.get_doc("Notification", notification_name)
    notification.send(doc)
