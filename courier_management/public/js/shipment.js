frappe.ui.form.on("Shipment", {
    refresh:(frm)=>{
        if(!frm.is_new()){
            frm.add_custom_button(__("Request Pickep Parcel"), ()=>{
                if(!frm.doc.awb_number){
                    frappe.throw("Docket No is not Generated.")
                }
                frappe.call({
                    method: "courier_management.courier_management.doc_events.shipment.booking_of_shipment",
                    args:{
                        doc : frm.doc
                    }
                })
            })
        }
    }
})