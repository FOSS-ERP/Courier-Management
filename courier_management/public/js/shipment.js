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
        if (!frm.doc.courier_partner || frm.doc.is_cancelled || !frm.doc.awb_number) 
        {
            return;
        }
        frappe.call({
            method: "courier_management.courier_management.doc_events.shipment.track_gati_awb",
            args: {
                doc: JSON.stringify(frm.doc),
                api_call: true
            },
            callback: function (r) {
                if (!r.message) {
                    console.warn("No response from GATI API");
                    return;
                }
                console.log("GATI Tracking API Response:", r.message)
            }
        });
    }
});
