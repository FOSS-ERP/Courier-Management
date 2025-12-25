frappe.ui.form.on("Shipment", {
    refresh:(frm)=>{
        if(!frm.doc.pickup_date){
            frm.set_value("pickup_date", frappe.datetime.get_today())
        }
        if (frm.doc.docstatus && frm.doc.shipment_id) {
            frm.add_custom_button(__("Cancel Pickup"), () => {
                frappe.confirm(
                    __("Are you sure you want to cancel this pickup booking?"),
                    function () {
                        frappe.call({
                            method: "courier_management.courier_management.doc_events.shipment.cancelle_pickup_booking",
                            args: {
                                doc: frm.doc
                            },
                            callback: (r) => {
                                if (r.message) {
                                    frm.reload_doc();
                                    frm.refresh_fields();
                                }
                            }
                        });
                    },
                    function () {
                        frappe.show_alert({ message: __("Cancellation Aborted"), indicator: "orange" });
                    }
                );
            });
        }

        if(frm.doc.docstatus == 1 && frm.doc.courier_partner && !frm.doc.shipment_id){
            frm.add_custom_button(__("Book Forward Pickup"),()=>{
                frappe.call({
                    method: "courier_management.courier_management.doc_events.shipment.book_shipment",
                    args:{
                        doc : frm.doc
                    },
                    freeze: true,
			        freeze_message:__("Booking your Parcel Shipment...."),
                    callback:(r)=>{
                        if(r.message){
                            frappe.dom.unfreeze();
                            frm.reload_doc()
                            frm.refresh_fields()
                        }
                    }
                })
            })
        }
        if(!frm.is_new() || frm.doc.docstatus == 1){
            frm.call({
                method: "courier_management.courier_management.doc_events.shipment.validate_pincode",  
                args: {
                    doc : frm.doc,
                    api_call : true,
                },
                callback: function(r) {
                    if (r.message && r.message.serviceDtls) {
                        const data = r.message.serviceDtls;
                        let html = `
                            <table class="table table-bordered table-sm">
                                <thead>
                                    <tr>
                                        <th>Location</th>
                                        <th>Location Code</th>
                                        <th>OU</th>
                                        <th>Service Type</th>
                                        <th>Distance</th>
                                        <th>ESS Category</th>
                                        <th>Transit Days</th>
                                    </tr>
                                </thead>
                                <tbody>`;
                        data.forEach(row => {
                            html += `
                                <tr>
                                    <td>${row.location}</td>
                                    <td>${row.locationCode}</td>
                                    <td>${row.ou}</td>
                                    <td>${row.serviceType}</td>
                                    <td>${row["distance "]}</td>
                                    <td>${row.essCatg}</td>
                                    <td>${row.transitDays}</td>
                                </tr>`;
                        });
    
                        html += `
                                </tbody>
                            </table>`;
                        frm.fields_dict.locations.$wrapper.html(html);
                    } else {
                        frm.fields_dict.locations.$wrapper.html('<p>No service details found.</p>');
                    }
                }
            });
        }
        if(!frm.is_new()){
            if(frm.doc.shipment_id && frm.doc.awb_number){
                frm.add_custom_button(__("Docket Print"),()=>{
                    if(frm.is_dirty()){
                        frappe.throw("First Save the document")
                    }
                    if(!frm.doc.awb_number){
                        frappe.throw("Docket No is not generated")
                    }
                    frappe.call({
                        method: "courier_management.courier_management.doc_events.shipment.docket_printing",
                        args:{
                            doc : frm.doc
                        },
                        callback:(r)=>{
                            if(r.message){
                                frm.reload_doc()
                                frm.refresh_fields()
                            }
                        }
                    })
                })
            }

        }
    },
    onload: (frm) => {
        if (!frm.doc.courier_partner || frm.doc.is_cancelled || !frm.doc.awb_number) {
            return;
        }

        frappe.call({
            method: "courier_management.courier_management.doc_events.shipment.track_gati_awb",
            args: {
                doc: JSON.stringify(frm.doc),
                api_call: true
            },
            callback: function (r) {
                if (!r.message) return;

                let data = r.message?.Gatiresponse?.dktinfo?.[0];
                if (!data) return;

                // -------- HEADER DETAILS --------
                let header_html = `
                    <h4>Docket Details</h4>
                    <table class="table table-bordered table-sm">
                        <tr><th>Docket No</th><td>${data.DOCKET_NUMBER}</td></tr>
                        <tr><th>Status</th><td>${data.DOCKET_STATUS}</td></tr>
                        <tr><th>Consignor</th><td>${data.CONSIGNOR_NAME}</td></tr>
                        <tr><th>Consignee</th><td>${data.CONSIGNEE_NAME}</td></tr>
                        <tr><th>Booking Station</th><td>${data.BOOKING_STATION}</td></tr>
                        <tr><th>Delivery Station</th><td>${data.DELIVERY_STATION}</td></tr>
                        <tr><th>Booked On</th><td>${data.BOOKED_DATETIME}</td></tr>
                        <tr><th>Weight</th><td>${data.ACTUAL_WEIGHT}</td></tr>
                        <tr><th>Packages</th><td>${data.NO_OF_PKGS}</td></tr>
                    </table>
                `;

                // -------- TRACKING HISTORY --------
                let timeline_rows = "";
                (data.TRANSIT_DTLS || []).forEach(row => {
                    timeline_rows += `
                        <tr>
                            <td>${row.INTRANSIT_DATE}</td>
                            <td>${row.INTRANSIT_TIME}</td>
                            <td>${row.INTRANSIT_LOCATION}</td>
                            <td>${row.INTRANSIT_STATUS}</td>
                        </tr>
                    `;
                });

                let transit_html = `
                    <h4>Tracking History</h4>
                    <table class="table table-bordered table-sm">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Time</th>
                                <th>Location</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${timeline_rows}
                        </tbody>
                    </table>
                `;

                // -------- FINAL HTML --------
                let final_html = header_html + transit_html;

                // -------- SAVE IN FIELD --------
                frm.set_value("tracking_details", final_html);
                frm.refresh_field("tracking_details");
            }
        });
    }

});
