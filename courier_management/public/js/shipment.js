frappe.ui.form.on("Shipment", {
    refresh:(frm)=>{
        if(!frm.is_new()){
            frm.call({
                method: "courier_management.courier_management.doc_events.shipment.validate_pincode",  
                args: {
                    self : frm.doc,
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
            if(frm.doc.courier_partner && !frm.is_dirty()){
                frm.add_custom_button(__("Request Pickep Parcel"), ()=>{
                    if(frm.is_dirty()){
                        frappe.throw("First Save the document")
                    }
                    if(!frm.doc.awb_number){
                        frappe.throw("Docket No is not Generated.")
                    }
                    frappe.call({
                        method: "courier_management.courier_management.doc_events.shipment.booking_of_shipment",
                        args:{
                            doc : frm.doc
                        },
                        callback(r){
                            if (r.message){
                                frm.refresh_field("shipment_id")
                            }
                        }
                    })
                })
            }
            if(frm.doc.shipment_id && frm.doc.awb_number && !frm.is_dirty()){
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
                            }
                        }
                    })
                })
            }
        }
    }
})
