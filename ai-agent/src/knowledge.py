"""
Structured knowledge base for UGVCL voice agent.

lookup(intent, text, lang) returns the most specific spoken answer for a
sub-topic within the intent, or None if only the generic intent reply applies.

Structure:
  _KB[intent] = list of (sub_keywords, {lang: answer})
The first entry whose sub_keywords all appear in the lowercased user text wins.
"""
import re

_KB: dict[str, list[tuple[list[str], dict[str, str]]]] = {

    # ─────────────────────────────── PAYMENT_HELP ─────────────────────────────
    "PAYMENT_HELP": [
        (["neft", "bank transfer", "bank of baroda", "ifsc", "virtual account"], {
            "gu-IN": "NEFT payment maate account number UGVCLLTZ pachhi 11 digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU. Payment 1-2 working days ma reflect thay.",
            "hi-IN": "NEFT ke liye account number UGVCLLTZ phir 11 digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU. Payment 1-2 working days mein reflect hoti hai.",
            "en-IN": "For NEFT: account UGVCLLTZ plus your 11-digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU. Reflects in 1-2 working days.",
        }),
        (["upi", "gpay", "phonepe", "paytm", "bhim"], {
            "gu-IN": "mpay.guvnl.in upar UPI thi payment karo — GPay, PhonePe, Paytm, BHIM badha chalse. Consumer number enter karo ne UPI select karo.",
            "hi-IN": "mpay.guvnl.in par UPI se payment karein — GPay, PhonePe, Paytm, BHIM sab chalte hain. Consumer number enter karein aur UPI select karein.",
            "en-IN": "Pay via UPI at mpay.guvnl.in — GPay, PhonePe, Paytm, BHIM all accepted. Enter consumer number and select UPI.",
        }),
        (["not reflect", "nathi aavyu", "payment dikhat nathi", "payment show", "payment confirm", "reflect nathi", "reflect nahi"], {
            "gu-IN": "Online payment 24 kalas ma reflect thay. NEFT ne 1-2 working days laage. 2 din pachhi pan na dikhe to aamaari billing team resolve karshe — tmaaro transaction ID taiyar raakho.",
            "hi-IN": "Online payment 24 ghante mein reflect hoti hai. NEFT ko 1-2 working days lagte hain. 2 din baad bhi na dikhe to hamari billing team resolve karegi — transaction ID taiyar rakhein.",
            "en-IN": "Online payment reflects within 24 hours. NEFT takes 1-2 working days. If not reflected after 2 days, our billing team will resolve it — please keep your transaction ID ready.",
        }),
        (["failed", "fail", "error", "unsuccessful", "payment thai nathi", "payment nahi hui"], {
            "gu-IN": "Payment fail thay to amount 5-7 working days ma bank ma parat aave. Fari try karo — aamaari billing team tmaari transaction review karshe.",
            "hi-IN": "Payment fail hone par amount 5-7 working days mein bank mein wapas aata hai. Dobara try karein — hamari billing team aapki transaction review karegi.",
            "en-IN": "Failed payments are refunded within 5-7 working days. Try again and our billing team will review your transaction.",
        }),
        (["cash", "cheque", "offline", "counter", "direct"], {
            "gu-IN": "UGVCL SDN office ma counter upar cash athva cheque thi payment kari shako. Office weekdays 10:30 AM thi 6 PM.",
            "hi-IN": "UGVCL SDN office ke counter par cash ya cheque se payment kar sakte hain. Office weekdays 10:30 AM se 6 PM tak.",
            "en-IN": "Pay by cash or cheque at any UGVCL SDN office counter, weekdays 10:30 AM to 6 PM.",
        }),
    ],

    # ─────────────────────────────── POWER_OUTAGE ─────────────────────────────
    "POWER_OUTAGE": [
        (["only my", "faqt mara", "sirf mera", "mara ghar ma", "mara ghar j"], {
            "gu-IN": "Sirf aapna ghar ni light bandi hoy to pehla MCB aane fuse check karo. Na chaale to tmaari complaint aamaari system ma register thayi chhe, field team 1-2 kalas ma aavse.",
            "hi-IN": "Sirf aapke ghar ki bijli gayi ho to pehle MCB aur fuse check karein. Na chale to aapki complaint hamare system mein register ho gayi hai, field team 1-2 ghante mein aayegi.",
            "en-IN": "If only your house has no power, first check MCB and fuse. If that doesn't help, your complaint is registered — our field team will arrive within 1-2 hours.",
        }),
        (["area", "street", "mohalla", "society", "colony", "aajubaju", "neighbourhood", "gali", "whole area"], {
            "gu-IN": "Aakhaa area ni outage complaint aamaari system ma register thayi chhe. Aamaro field team kaam kar rahyo chhe, 2-4 kalas ma supply restore thase.",
            "hi-IN": "Poore area ki outage complaint hamare system mein register ho gayi hai. Hamara field team kaam kar raha hai, 2-4 ghante mein supply restore hogi.",
            "en-IN": "Area-wide outage complaint is registered in our system. Our field team is working on it, supply will be restored within 2-4 hours.",
        }),
        (["planned", "schedule", "maintenance", "maintenance shutdown", "notified", "jadvu", "jadu"], {
            "gu-IN": "Planned maintenance shutdown ni info pehela thi local SDN office ma milse. Scheduled maintenance hoy to advance notice aapvama aavse.",
            "hi-IN": "Planned maintenance ki jaankari pehle se SDN office mein milti hai. Scheduled maintenance par advance notice di jaati hai.",
            "en-IN": "Planned maintenance shutdown information is available at your local SDN office. Advance notice is provided for scheduled maintenance.",
        }),
        (["mcb", "fuse", "trip", "elcb", "main switch"], {
            "gu-IN": "MCB trip thayo hoy to switch reset karo. Baar baar trip thay to wiring check karaavo — electrical fault hoi shake chhe. Wiring fault complaint aamaari system ma register thayi chhe.",
            "hi-IN": "MCB trip hua ho to switch reset karein. Baar baar trip ho to wiring check karaayein — fault ho sakta hai. Wiring fault complaint hamare system mein register ho gayi hai.",
            "en-IN": "If MCB has tripped, reset the switch. If it trips repeatedly, get your wiring checked — there may be a fault. Your wiring fault complaint is registered in our system.",
        }),
        (["transformer", "pole", "wire broken", "wire fault", "line fault"], {
            "gu-IN": "Tmaari transformer fault complaint aamaari system ma register thayi chhe. Broken wire athva pole pashe bilkul nahi jao — khatarnak chhe. Aamaro field team vadhare leti 2-3 kalas ma aavshe.",
            "hi-IN": "Aapki transformer fault complaint hamare system mein register ho gayi hai. Tuti line ya pole ke paas bilkul mat jayein — khatarnak hai. Hamara field team 2-3 ghante mein aayega.",
            "en-IN": "Your transformer fault complaint is registered in our system. Do not go near broken wires or poles — it is dangerous. Our field team will arrive within 2-3 hours.",
        }),
    ],

    # ─────────────────────────────── BILL_INFO ────────────────────────────────
    "BILL_INFO": [
        (["download", "copy", "duplicate", "pdf", "bill copy", "bill download"], {
            "gu-IN": "Bill copy mpay.guvnl.in upar login kari Consumer section ma Download Bill option thi melo. SMS ma link pan aave.",
            "hi-IN": "Bill copy mpay.guvnl.in par login karke Consumer section mein Download Bill option se prapt karein.",
            "en-IN": "Download your bill copy from mpay.guvnl.in — log in and go to Consumer section, Download Bill.",
        }),
        (["due date", "last date", "jama karvani", "deadline", "kyare bharvo", "kab tak"], {
            "gu-IN": "Bill ni due date bill print upar hoy chhe. Smart meter consumers ne monthly 20-25 tarikh sudhima due date aave.",
            "hi-IN": "Bill ki due date bill print par hoti hai. Smart meter consumers ke liye monthly 20-25 tarikh tak due date hoti hai.",
            "en-IN": "Your bill due date is printed on the bill. Smart meter consumers typically have due dates around the 20th to 25th of each month.",
        }),
        (["reading", "meter reading", "unit consumed", "units", "reading kevi"], {
            "gu-IN": "Meter reading SDN office athva smart meter app ma dikhe. Bill upar previous aane current reading print thayeli hoy chhe.",
            "hi-IN": "Meter reading SDN office ya smart meter app mein dekh sakte hain. Bill par previous aur current reading printed hoti hai.",
            "en-IN": "Meter reading is shown in the SDN office or smart meter app. Previous and current readings are printed on your bill.",
        }),
        (["slab", "tariff", "rate", "unit rate", "per unit", "charges", "duty", "tax"], {
            "gu-IN": "UGVCL tariff slab ugvcl.com upar Tariff section ma milse. LT Domestic consumers ne 0-50 unit, 51-200 unit ne 200+ unit sudhina alag alag rate lagu pade.",
            "hi-IN": "UGVCL tariff slab ugvcl.com par Tariff section mein milti hai. LT Domestic consumers ke liye 0-50, 51-200 aur 200+ units ke alag rate hain.",
            "en-IN": "UGVCL tariff slabs are available on ugvcl.com under the Tariff section. LT Domestic consumers have different rates for 0-50, 51-200, and 200+ units.",
        }),
    ],

    # ─────────────────────────────── RECONNECTION ─────────────────────────────
    "RECONNECTION": [
        (["how long", "ketla din", "ketla time", "kitne din", "kitne time", "time lagse", "days lagse"], {
            "gu-IN": "Payment verify thaya bad 2-3 working days ma connection restore thay. Urgent hoy to SDN office ma personally jao — same day process thashe.",
            "hi-IN": "Payment verify hone ke 2-3 working days mein connection restore ho jata hai. Urgent ho to SDN office mein personally jayein — same day process hogi.",
            "en-IN": "Connection is restored within 2-3 working days after payment is verified. For urgent cases, visit SDN office in person for same-day processing.",
        }),
        (["partial", "part payment", "thodu", "advance", "half payment"], {
            "gu-IN": "Partial payment thi reconnection thai nathi. Pooro baki amount bharo pachhi j 2-3 days ma connection aavse.",
            "hi-IN": "Partial payment se reconnection nahi hoti. Poora baki amount bhar dein, tab 2-3 days mein connection aayega.",
            "en-IN": "Reconnection does not happen on partial payment. Pay the full outstanding amount; connection restores in 2-3 working days.",
        }),
        (["emergency", "hospital", "urgent", "serious", "jaldi", "turant", "abhi"], {
            "gu-IN": "Medical emergency maate SDN office ma payment proof sathe personally jao — emergency reconnection same day process thashe. Tmaari urgent request aamaari system ma note thayi chhe.",
            "hi-IN": "Medical emergency ke liye SDN office mein payment proof leke personally jayein — emergency reconnection same day process hogi. Aapki urgent request hamare system mein note ho gayi hai.",
            "en-IN": "For medical emergencies, visit SDN office in person with payment proof — emergency reconnection is processed same day. Your urgent request is noted in our system.",
        }),
        (["not done", "nathi thayun", "nahi hui", "still not", "abhi tak nahi", "pan nathi aavy"], {
            "gu-IN": "2-3 working days pachhi pan connection na thayun hoy to tmaari complaint aamaari team escalate karshe — payment receipt taiyar raakho.",
            "hi-IN": "2-3 working days ke baad bhi connection na ho to hamari team aapki complaint escalate karegi — payment receipt taiyar rakhein.",
            "en-IN": "If connection is not restored after 2-3 working days, our team will escalate your complaint — please keep your payment receipt ready.",
        }),
    ],

    # ─────────────────────────────── SOLAR_BILLING ────────────────────────────
    "SOLAR_BILLING": [
        (["calculate", "ganit", "formula", "how", "kevi rite", "kaise"], {
            "gu-IN": "Solar bill: Import units minus Export units equal net units. Net units upar tariff rate laagse. Excess export units carry forward athva June ma credit.",
            "hi-IN": "Solar bill: Import units minus Export units barabar net units. Net units par tariff rate lagta hai. Excess export units carry forward ya June mein credit.",
            "en-IN": "Solar bill = Import units minus Export units = net units billed at tariff rate. Excess export units carry forward and are settled in June.",
        }),
        (["credit", "excess", "settlement", "june", "bank credit", "account credit"], {
            "gu-IN": "Excess export amount dar varse June mahina ma bank account ma automatically credit thay. SDN office ma bank details update karavi raakho.",
            "hi-IN": "Excess export amount har saal June mein bank account mein automatically credit hoti hai. SDN office mein bank details update rakhein.",
            "en-IN": "Excess export amount is credited to your bank account automatically every June. Keep your bank details updated at SDN office.",
        }),
        (["net meter", "bidirectional", "meter reading", "meter install"], {
            "gu-IN": "Net meter import aane export alag alag record kare. Meter upar do reading dikhe — import aane export. Difference upar billing.",
            "hi-IN": "Net meter import aur export alag record karta hai. Meter par do readings dikhti hain — import aur export. Difference par billing.",
            "en-IN": "Net meter records import and export separately. Two readings appear on the meter — import and export. Billing is on the difference.",
        }),
        (["rooftop", "panel", "install", "apply", "new solar", "solar lavo", "solar lagavvu"], {
            "gu-IN": "Rooftop solar installation maate UGVCL SDN office ma application karo. Net metering connection maate approval levo padse. ugvcl.com upar Solar section juo.",
            "hi-IN": "Rooftop solar ke liye UGVCL SDN office mein application karein. Net metering connection ke liye approval lena hoga.",
            "en-IN": "Apply for rooftop solar at your UGVCL SDN office. You will need approval for net metering connection. Check Solar section on ugvcl.com.",
        }),
    ],

    # ─────────────────────────────── SMART_METER ──────────────────────────────
    "SMART_METER": [
        (["app", "mobile app", "ugvcl app", "open nathi", "not working", "login"], {
            "gu-IN": "UGVCL smart meter app kaam na kare to pehla update check karo. Fari na chale to tmaari complaint register thayi chhe — technician 24-48 kalaak ma visit karshe.",
            "hi-IN": "UGVCL smart meter app kaam na kare to pehle update check karein. Phir bhi na chale to aapki complaint register ho gayi hai — technician 24-48 ghante mein visit karega.",
            "en-IN": "If UGVCL smart meter app is not working, first check for app updates. If it still fails, your complaint is registered — technician will visit within 24-48 hours.",
        }),
        (["mandatory", "compulsory", "forced", "jaruri", "faraz", "forcefully"], {
            "gu-IN": "Smart meter bharat sarkar na Electricity Ministry na RDSS scheme ane NIT Directive anusar mandatory chhe. Consumer ni individual sahmat ni jaroorat nathi.",
            "hi-IN": "Smart meter Bharat Sarkar ke RDSS scheme aur NIT Directive anusar mandatory hai. Consumer ki individual sahmat ki zaroorat nahi.",
            "en-IN": "Smart meters are mandatory under the Government of India RDSS scheme and NIT Directive. Individual consumer consent is not required.",
        }),
        (["reading wrong", "reading galat", "reading khothi", "billing wrong"], {
            "gu-IN": "Smart meter reading galat lage to SDN office ma meter reading dispute form bharo — technician meter verify karshe. Tmaari dispute complaint note thayi chhe.",
            "hi-IN": "Smart meter reading galat lage to SDN office mein meter reading dispute form bharein — technician meter verify karega. Aapki dispute complaint note ho gayi hai.",
            "en-IN": "If smart meter reading seems wrong, submit a meter reading dispute form at SDN office — a technician will verify. Your dispute complaint is noted.",
        }),
        (["tamper", "seal", "broken", "damage", "kharab", "chor"], {
            "gu-IN": "Meter tamper athva seal toda hoy to tmaari complaint turant aamaari technical team ne moksavi chhe. Tampered meter par penalty lagi shake chhe.",
            "hi-IN": "Meter tamper ya seal tuta ho to aapki complaint turant hamare technical team ko bheji gayi hai. Tampered meter par penalty lag sakti hai.",
            "en-IN": "Meter tamper or broken seal complaint has been urgently sent to our technical team. Note: penalty may be applicable for tampered meters.",
        }),
        (["prepaid smart", "smart prepaid", "balance dikhe nathi", "balance not showing"], {
            "gu-IN": "Prepaid smart meter balance check maate UGVCL app athva mpay.guvnl.in upar Consumer Dashboard juo. Balance zero thay tyare auto-disconnect thay.",
            "hi-IN": "Prepaid smart meter balance check ke liye UGVCL app ya mpay.guvnl.in par Consumer Dashboard dekhein.",
            "en-IN": "Check prepaid smart meter balance on the UGVCL app or Consumer Dashboard at mpay.guvnl.in. Supply disconnects automatically when balance reaches zero.",
        }),
    ],

    # ─────────────────────────────── PREPAID ──────────────────────────────────
    "PREPAID": [
        (["recharge kevi rite", "how to recharge", "recharge process", "recharge kyat", "recharge kahan"], {
            "gu-IN": "Prepaid recharge maate mpay.guvnl.in upar consumer number enter karo, amount nakkhi karo, UPI athva card thi pay karo. 3% rebate marse.",
            "hi-IN": "Prepaid recharge ke liye mpay.guvnl.in par consumer number enter karein, amount chune, UPI ya card se pay karein. 3% rebate milega.",
            "en-IN": "To recharge prepaid, go to mpay.guvnl.in, enter consumer number, choose amount, and pay by UPI or card. You get 3% rebate.",
        }),
        (["balance check", "balance jovu", "balance ketu", "balance ketlu", "balance dekhna"], {
            "gu-IN": "Prepaid balance mpay.guvnl.in upar login kari Consumer Dashboard ma athva UGVCL app ma dikhe.",
            "hi-IN": "Prepaid balance mpay.guvnl.in par login karke Consumer Dashboard ya UGVCL app mein dekhein.",
            "en-IN": "Check prepaid balance at mpay.guvnl.in Consumer Dashboard or on the UGVCL app.",
        }),
        (["low balance", "alert", "warning", "thodu baki", "balance kam", "disconnect thashe"], {
            "gu-IN": "Balance 100 rupia niche aavse tyare SMS alert aavse. Supply disconnect thavani ek kalaak pehela pan SMS aavse. Tarat recharge karo.",
            "hi-IN": "Balance 100 rupaye se neeche aane par SMS alert aata hai. Supply disconnect hone se ek ghante pehle bhi SMS aata hai. Turant recharge karein.",
            "en-IN": "An SMS alert is sent when balance drops below Rs 100. Another SMS is sent one hour before disconnection. Recharge promptly.",
        }),
        (["not reflect", "recharge thai nathi", "recharge nahi hua", "recharge stuck", "recharge show nathi"], {
            "gu-IN": "Recharge 2 kalas ma reflect na thay to tmaari complaint note thayi chhe — transaction ID taiyar raakho, aamaari billing team resolve karshe.",
            "hi-IN": "Recharge 2 ghante mein reflect na ho to aapki complaint note ho gayi hai — transaction ID taiyar rakhein, hamari billing team resolve karegi.",
            "en-IN": "If recharge does not reflect within 2 hours, your complaint is noted — keep your transaction ID ready, our billing team will resolve it.",
        }),
        (["rebate", "discount", "benefit", "3 percent", "3%"], {
            "gu-IN": "Prepaid consumers ne energy charge upar 3 percent rebate automatically apply thay. No minimum recharge — koi bhi amount rechargeable.",
            "hi-IN": "Prepaid consumers ko energy charge par 3 percent rebate automatically apply hoti hai. Koi minimum recharge nahi.",
            "en-IN": "Prepaid consumers automatically get 3 percent rebate on energy charges. There is no minimum recharge amount.",
        }),
    ],

    # ─────────────────────────────── NEW_CONNECTION ───────────────────────────
    "NEW_CONNECTION": [
        (["document", "kagad", "dastavej", "what to bring", "kya chahiye", "shu joie"], {
            "gu-IN": "New connection maate: Aadhaar card, property index copy athva ownership proof, site plan sketch aane LT New Connection Application form SDN office ma submit karo.",
            "hi-IN": "New connection ke liye: Aadhaar card, property index copy ya ownership proof, site plan sketch aur LT New Connection Application form SDN office mein submit karein.",
            "en-IN": "For new connection bring: Aadhaar card, property index copy or ownership proof, site plan sketch, and LT New Connection Application form to SDN office.",
        }),
        (["time", "kitna samay", "ketla din", "how long", "process kitno", "process time"], {
            "gu-IN": "Application submit pachhi: Feasibility visit 7-10 working days, work order jari, payment pachhi connection 15-30 days ma.",
            "hi-IN": "Application submit karne ke baad: Feasibility visit 7-10 working days, work order jaari, payment ke baad 15-30 days mein connection.",
            "en-IN": "After submitting application: feasibility visit in 7-10 working days, then work order, then connection within 15-30 days after payment.",
        }),
        (["online apply", "online application", "website", "portal", "without office"], {
            "gu-IN": "ugvcl.com upar Consumer, Online Service, New Connection section thi online application submit kari shako chho.",
            "hi-IN": "ugvcl.com par Consumer, Online Service, New Connection section se online application submit kar sakte hain.",
            "en-IN": "Apply online at ugvcl.com — go to Consumer, Online Service, and select New Connection.",
        }),
        (["load", "kw", "kilowatt", "load change", "load increase", "load vadharvu"], {
            "gu-IN": "Load change maate SDN office ma written application — current load ne required load sathe. Technical feasibility check thashe.",
            "hi-IN": "Load change ke liye SDN office mein written application — current load aur required load ke saath. Technical feasibility check hogi.",
            "en-IN": "For load change, submit a written application at SDN office stating current and required load. Technical feasibility will be checked.",
        }),
    ],

    # ─────────────────────────────── HIGH_BILL ────────────────────────────────
    "HIGH_BILL": [
        (["dispute", "complain", "contest", "wrong", "galat", "khothi", "ghalat"], {
            "gu-IN": "Bill dispute maate bill date na 5 din ni andar SDN office jao: meter KWH photo, consumer number, Aadhaar card aane bill copy sathe written application.",
            "hi-IN": "Bill dispute ke liye bill date ke 5 din mein SDN office jayein: meter KWH photo, consumer number, Aadhaar card aur bill copy ke saath written application.",
            "en-IN": "To dispute bill, visit SDN office within 5 days of bill date with meter KWH photo, consumer number, Aadhaar card, and bill copy.",
        }),
        (["average", "estimated", "estimated bill", "meter not read", "reading nai lidhi"], {
            "gu-IN": "Meter reading na mle tyare average billing aapvama aave. Next meter reading par actual units adjust thay. SDN office ma reading update karavvo.",
            "hi-IN": "Meter reading na mile to average billing diya jata hai. Next actual reading par units adjust ho jaati hain.",
            "en-IN": "When meter reading is unavailable, average billing is applied. Units are adjusted on the next actual reading. Visit SDN office to update reading.",
        }),
        (["reason", "keva maate vadhyo", "kyun zyada", "sudden increase", "ekdam vadi gayu"], {
            "gu-IN": "Bill vadhvana karan: season change, extra appliance, meter reading backlog, athva tariff revision. Meter reading verify karo ne previous bills compare karo.",
            "hi-IN": "Bill badhne ke karan: season change, extra appliance, meter reading backlog, ya tariff revision. Meter reading verify karein aur purane bills se compare karein.",
            "en-IN": "Bill may increase due to seasonal usage, extra appliances, backlogged readings, or tariff revision. Verify meter reading and compare with previous bills.",
        }),
        (["solar", "solar bill high", "import vadhu"], {
            "gu-IN": "Solar consumers nu bill high hoy to import units aane export units fari check karo. Net meter reading correct chhe ke nai verify karo. Tmaari billing dispute note thayi chhe.",
            "hi-IN": "Solar consumers ka bill zyada ho to import aur export units dobara check karein. Net meter reading verify karein. Aapki billing dispute note ho gayi hai.",
            "en-IN": "For high solar bills, verify import and export unit readings and ensure net meter readings are correct. Your billing dispute has been noted.",
        }),
    ],

    # ─────────────────────────────── MOBILE_REG ───────────────────────────────
    "MOBILE_REG": [
        (["otp", "otp nathi aavtu", "otp not received", "verification", "otp aavtu nathi"], {
            "gu-IN": "OTP na aave to number correct chhe ke nai check karo. 2 minute wait karo, fari try karo. Problem rahe to tmaari issue aamaari support team ne moksavama aavse.",
            "hi-IN": "OTP na aaye to number sahi hai ki nahi check karein. 2 minute wait karein, phir try karein. Problem rahe to hamari support team handle karegi.",
            "en-IN": "If OTP is not received, verify the number is correct. Wait 2 minutes and try again. If the problem persists, our support team will handle it.",
        }),
        (["update", "change number", "number badlavu", "number change", "new number"], {
            "gu-IN": "Mobile number change maate ugvcl.com upar Consumer, Online Service, Link Mobile ma navo number enter karo aane OTP verify karo.",
            "hi-IN": "Mobile number change ke liye ugvcl.com par Consumer, Online Service, Link Mobile mein naya number enter karein aur OTP verify karein.",
            "en-IN": "To change mobile number, go to ugvcl.com, Consumer, Online Service, Link Mobile, enter new number and verify OTP.",
        }),
        (["sms not coming", "sms nathi aavti", "sms band", "notification"], {
            "gu-IN": "SMS na aavti hoy to mobile number register chhe ke nai check karo. ugvcl.com upar Link Mobile section ma registered number confirm karo.",
            "hi-IN": "SMS na aaye to mobile number registered hai ya nahi check karein. ugvcl.com par Link Mobile section mein registered number confirm karein.",
            "en-IN": "If SMS is not coming, check if your mobile number is registered. Confirm on ugvcl.com under Link Mobile section.",
        }),
    ],

    # ─────────────────────────────── REFUND ───────────────────────────────────
    "REFUND": [
        (["process", "kevi rite", "how", "apply kevi"], {
            "gu-IN": "Refund maate SDN office ma application, payment receipt, bank statement aane Aadhaar card submit karo. Refund original payment gateway upar 7-10 working days ma aavse.",
            "hi-IN": "Refund ke liye SDN office mein application, payment receipt, bank statement aur Aadhaar card jama karein. 7-10 working days mein original gateway par refund aata hai.",
            "en-IN": "For refund, submit application, payment receipt, bank statement, and Aadhaar card at SDN office. Refund processed to original gateway in 7-10 working days.",
        }),
        (["double payment", "paid twice", "duplicate payment", "be var payment", "do baar payment"], {
            "gu-IN": "Double payment hoy to donni payment receipts aane bank statement SDN office ma submit karo. Extra amount 7-10 working days ma refund thashe.",
            "hi-IN": "Double payment ho to dono payment receipts aur bank statement SDN office mein submit karein. Extra amount 7-10 working days mein refund hoga.",
            "en-IN": "For double payment, submit both payment receipts and bank statement at SDN office. Extra amount will be refunded in 7-10 working days.",
        }),
        (["time", "ketla din", "how long", "kab aayega", "kyare aavse"], {
            "gu-IN": "Approved refund 7-10 working days ma original payment gateway upar aavse. NEFT refund ne vadhare time lagi shake.",
            "hi-IN": "Approved refund 7-10 working days mein original payment gateway par aata hai. NEFT refund mein thoda zyada time lag sakta hai.",
            "en-IN": "Approved refunds arrive within 7-10 working days to the original payment gateway. NEFT refunds may take slightly longer.",
        }),
    ],

    # ─────────────────────────────── NAME_ADDRESS ─────────────────────────────
    "NAME_ADDRESS": [
        (["name change", "naam badlav", "naam correct", "wrong name", "naam khothu"], {
            "gu-IN": "Name change maate SDN office ma application, Aadhaar card, property document aane bill copy submit karo. Verification pachhi 15 working days ma update.",
            "hi-IN": "Name change ke liye SDN office mein application, Aadhaar card, property document aur bill copy submit karein. Verification ke baad 15 working days mein update.",
            "en-IN": "For name change, submit application, Aadhaar card, property document, and bill copy at SDN office. Updated within 15 working days after verification.",
        }),
        (["address change", "address correct", "address badlav", "address khothi"], {
            "gu-IN": "Address change maate SDN office ma application, Aadhaar card aane property document submit karo.",
            "hi-IN": "Address change ke liye SDN office mein application, Aadhaar card aur property document submit karein.",
            "en-IN": "For address change, submit application, Aadhaar card, and property document at SDN office.",
        }),
        (["death", "mrutyu", "deceased", "owner died", "malak gaya"], {
            "gu-IN": "Consumer nu death thayun hoy to SDN office ma death certificate, heir's Aadhaar, property document sathe name transfer application submit karo.",
            "hi-IN": "Consumer ka nidhan hua ho to SDN office mein death certificate, waris ka Aadhaar, property document ke saath name transfer application submit karein.",
            "en-IN": "For deceased consumer name transfer, submit death certificate, heir's Aadhaar, and property documents at SDN office.",
        }),
    ],

    # ─────────────────────────────── OFFICE_INFO ──────────────────────────────
    "OFFICE_INFO": [
        (["time", "hours", "timing", "kela vaage", "kaaj na kaaj na", "opening", "closing", "when open"], {
            "gu-IN": "UGVCL SDN office Monday thi Saturday, 10:30 AM thi 6:00 PM. Sunday aane public holiday band. After-hours emergency maate aamaari AI helpline 24/7 available chhe.",
            "hi-IN": "UGVCL SDN office Monday se Saturday, 10:30 AM se 6:00 PM. Sunday aur public holiday band. After-hours emergency ke liye hamari AI helpline 24/7 available hai.",
            "en-IN": "UGVCL SDN office is open Monday to Saturday, 10:30 AM to 6:00 PM. Closed on Sundays and public holidays. For after-hours emergencies, our AI helpline is available 24/7.",
        }),
        (["address", "kyat", "kahan", "location", "where", "place", "nearest"], {
            "gu-IN": "Nearest SDN office no address ugvcl.com upar Office Locator section ma milse. Tmaaro pincode enter karo ne nearest office milshe.",
            "hi-IN": "Nearest SDN office ka address ugvcl.com par Office Locator section mein milega. Apna pincode enter karein aur nearest office milega.",
            "en-IN": "Find your nearest SDN office address on ugvcl.com under the Office Locator section. Enter your pincode to find the closest office.",
        }),
    ],

    # ─────────────────────────────── BILLING_FREQ ─────────────────────────────
    "BILLING_FREQ": [
        (["change", "monthly karvun", "bi-monthly thavun", "can I change", "badlai shakay"], {
            "gu-IN": "Smart meter consumers ne billing frequency badlavi shakati nathi — mandatory monthly. Non-smart meter consumers ne bi-monthly billing automatic.",
            "hi-IN": "Smart meter consumers ke liye billing frequency nahi badal sakti — mandatory monthly. Non-smart meter consumers ke liye bi-monthly automatic.",
            "en-IN": "Smart meter consumers cannot change billing frequency — monthly billing is mandatory. Non-smart meter consumers automatically receive bi-monthly bills.",
        }),
        (["quarterly", "3 month", "teen mahine", "tintrima"], {
            "gu-IN": "UGVCL quarterly billing provide karti nathi. Smart meter consumers ne monthly aane baaki ne bi-monthly.",
            "hi-IN": "UGVCL quarterly billing nahi deta. Smart meter consumers ko monthly aur baaki ko bi-monthly.",
            "en-IN": "UGVCL does not offer quarterly billing. Smart meter consumers receive monthly bills; others receive bi-monthly bills.",
        }),
    ],

    # ─────────────────────────────── COMPLAINT_NUMBER ─────────────────────────
    "COMPLAINT_NUMBER": [
        (["toll free", "free call", "helpline", "number", "contact"], {
            "gu-IN": "UGVCL toll-free helpline: 19121 athva 1800-233-155-335. 24 kalaak 7 din available. Mobile, landline — badhe thi free.",
            "hi-IN": "UGVCL toll-free helpline: 19121 ya 1800-233-155-335. 24 ghante 7 din available. Mobile, landline — sabse free.",
            "en-IN": "UGVCL toll-free helpline: 19121 or 1800-233-155-335. Available 24 hours, 7 days. Free from mobile and landline.",
        }),
        (["online complaint", "website complaint", "portal complaint"], {
            "gu-IN": "Online complaint ugvcl.com upar Book Complaint section ma karo. Complaint number malshe — track kari shaksho.",
            "hi-IN": "Online complaint ugvcl.com par Book Complaint section mein darj karein. Complaint number milega — track kar sakte hain.",
            "en-IN": "Register online complaint at ugvcl.com under Book Complaint section. You will receive a complaint number to track status.",
        }),
        (["whatsapp", "email", "chat", "social media"], {
            "gu-IN": "UGVCL ni official whatsapp athva chat service nathi. 19121 upar call athva ugvcl.com upar complaint karo.",
            "hi-IN": "UGVCL ki official WhatsApp ya chat service nahi hai. 19121 par call ya ugvcl.com par complaint karein.",
            "en-IN": "UGVCL does not have an official WhatsApp or chat service. Call 19121 or file complaint at ugvcl.com.",
        }),
    ],
}


def _word_match(kw: str, text_lower: str) -> bool:
    """Match keyword as whole word(s) to avoid substring false positives like 'app' in 'happy'."""
    return bool(re.search(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', text_lower))


def lookup(intent: str, text: str, lang: str) -> str | None:
    """
    Return a specific spoken answer if the user text matches a sub-topic keyword group,
    or None if only the generic intent reply applies.

    Matching: ANY keyword in the group appearing as a whole word is a hit.
    Groups are ordered most-specific first so the first match wins.
    """
    entries = _KB.get(intent)
    if not entries:
        return None

    lower = text.lower()
    for keywords, replies in entries:
        if any(_word_match(kw, lower) for kw in keywords):
            answer = replies.get(lang) or replies.get("en-IN")
            return answer

    return None
