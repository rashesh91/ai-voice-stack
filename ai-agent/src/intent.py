"""
Intent classifier and reply builder for UGVCL voice agent.
Supports Gujarati, Hindi, and English with randomised conversational responses.
"""
import random

# ---------------------------------------------------------------------------
# Intent keyword matching
# ---------------------------------------------------------------------------
_INTENT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("BILL_INFO", [
        "bill ketu", "bill ketlu", "bill amount", "bill info", "bill jovu",
        "bill janavvu", "maru bill", "aapmnu bill", "bill che ketlu",
        "bill kyare", "current bill", "mane bill", "bill baki",
        "bill kiti", "bill kem", "maro bill",
        "outstanding", "arrear", "pending amount", "due amount",
        "bill vishe", "bill vishhe", "bill vishshe", "bill baabat", "bill ni",
        "bill jaankari", "bill maahiti", "bill thayu", "bill ketlo",
        "bill jankari", "bill check", "bill joi", "bill jou",
        "bill no", "bill ange", "bill info",
        "બિલ", "bill કેટ", "bill બાકી", "મારું bill", "bill kem",
        "bill baaki", "baaki bill", "bill aavyo", "bill aavshhe",
        "મારા bill", "bill વિશે", "bill ની",
        "mera bill", "bill kitna", "bill batao", "baaki bill", "baki kitna",
        "बिल", "बिल कितना", "बकाया", "bill ke baare",
        "my bill", "bill amount", "how much bill", "current bill",
        "outstanding bill", "pending bill", "bill details",
    ]),
    ("PAYMENT_HELP", [
        "bill bharvo", "payment", "bharvu", "online pay", "neft", "mpay",
        "bill kevi rite", "kevi rite bharvo", "payment link", "pay kari",
        "payment karvo", "online bharo", "kyan bharvo", "payment method",
        "virtual account", "bank of baroda", "ifsc",
        "ચૂકવ", "ભરવ", "ભુગ", "mpay", "ઓનલાઇન pay",
        "bill kaise bharein", "payment kaise", "online payment",
        "भुगतान", "पेमेंट",
        "how to pay", "pay bill", "payment options", "neft transfer",
    ]),
    ("POWER_OUTAGE", [
        "light nathi", "light band", "vij nathi", "power cut",
        "light nai", "light aavre nai", "power off", "supply band",
        "light bujhi", "vij band",
        "light નથી", "લાઈટ નથી", "વીજ નથી", "light બંધ",
        "અંધારું", "current nathi",
        "transformer", "ટ્રાન્સફોર્મર", "pole fault", "line fault",
        "wire broken", "wire fault", "mcb trip", "fuse gayo",
        "bijli nahi", "light nahi", "power nahi", "bijli gayi",
        "transformer jal", "line tut", "bijli fault",
        "no power", "power outage", "electricity gone", "no electricity",
        "transformer burnt", "transformer fault", "line down",
    ]),
    ("SOLAR_BILLING", [
        "solar", "solar bill", "solar meter", "net meter",
        "import unit", "export unit", "solar system",
        "solar nu bill", "solarnu bill", "solar export",
        "solar generate", "rooftop solar", "solar panel",
        "solar ka bill",
        "solar billing", "solar calculation", "net metering",
    ]),
    ("SMART_METER", [
        "smart meter", "meter issue", "app open nathi", "ugvcl app",
        "meter reading", "smart meter complaint", "meter rite chalto nathi",
        "meter kaam nathi", "meter chal nathi",
        "મીટર ખરાબ", "smart meter ખરાબ", "smart meter app", "મીટર",
        "मीटर", "स्मार्ट मीटर",
        "smart meter problem", "meter not working", "meter complaint",
    ]),
    ("RECONNECTION", [
        "reconnect", "connection cut", "light aavse kyare", "kyare aavse",
        "bill bharya pachi", "supply restore", "connection restore",
        "disconnect thayo", "supply bai", "connection bai",
        "ક્યારે આવશે", "light ક્યારે", "reconnection",
        "connection kab aayega", "bijli kab aayegi",
        "when will power come", "reconnect service",
    ]),
    ("PREPAID", [
        "prepaid balance", "balance zero", "balance check", "recharge",
        "prepaid meter", "prepaid", "balance ketu", "balance ketlu",
        "recharge kevi rite", "balance janavvu", "balance",
        "પ્રીપેઇડ", "recharge link",
        "prepaid recharge", "check balance", "prepaid account",
    ]),
    ("NEW_CONNECTION", [
        "new connection", "navu connection", "navu jodavo", "apply connection",
        "navi line", "connection levun", "connection apply",
        "નવું connection", "connection aapvo",
        "naya connection", "connection chahiye",
        "new electricity connection", "apply for connection",
    ]),
    ("MOBILE_REG", [
        "mobile register", "mobile number", "link mobile", "mobile link",
        "number register", "sms nathi aavti", "sms alert",
        "otp nathi aavtu", "otp nahi", "otp not", "otp",
        "mobile nondh",
        "mobile નોંધ", "number update",
        "register mobile", "update mobile number", "mobile sms",
    ]),
    ("HIGH_BILL", [
        "bill vadhu", "bill vadhare", "reading khothi", "reading ghalat",
        "meter reading", "bill correct", "high bill", "bill vadu",
        "reading wrong", "bill motu", "reading verify",
        "bill ઘણું", "ઊંચો bill", "bill vadharo",
        "bill bahut zyada", "galat reading",
        "wrong reading", "disputed bill", "meter reading wrong",
    ]),
    ("BILLING_FREQ", [
        "quarterly billing", "bi-monthly", "billing interval",
        "monthly ни jagae", "monthly ni jagye", "billing change",
        "quarterly", "2 mahine nu bill", "monthly billing badlavu",
        "billing monthly", "quarterly karvun",
        "change billing frequency", "quarterly bill", "bimonthly",
    ]),
    ("REFUND", [
        "refund", "paise pachi", "return paise", "refund kevi",
        "paise parat", "amount return", "refund apply",
        "paisa wapas", "refund chahiye",
        "get refund", "money back", "refund process",
    ]),
    ("NAME_ADDRESS", [
        "name change", "naam badlav", "naam khothu", "address change",
        "address khothi", "naam correct", "address correct",
        "naam update", "address update",
        "નામ ખોટ", "address ખોટ",
        "wrong name", "name correction", "address change",
    ]),
    ("OFFICE_INFO", [
        "sdn office", "office kyat", "office time", "office kya",
        "office address", "office javu", "office info",
        "SDN", "ઓફિસ", "office hours",
        "office location", "where is office", "office timing",
    ]),
    ("COMPLAINT_NUMBER", [
        "toll free", "complaint number", "helpline", "19121",
        "customer care number", "contact number",
        "ફરિયાદ ક્યાં", "complaint kyat",
        "helpline number", "complaint contact",
    ]),
]

# ---------------------------------------------------------------------------
# Multilingual replies — lists for random variety, shorter punchy sentences
# ---------------------------------------------------------------------------
_REPLIES: dict = {
    "BILL_INFO": {
        "gu-IN": [
            "{name} ji, tamaro {plan} plan nu bill {bill_amount} chhe — {due_date} sudhi bharjo.{notes_suffix}",
            "Ji {name} ji! {plan} account nu {bill_amount} baki chhe, {due_date} pehla bharo.{notes_suffix}",
            "{name} ji, {plan} nu bill {bill_amount} chhe. {due_date} sudhi bharo ne.{notes_suffix}",
        ],
        "hi-IN": [
            "{name} ji, aapka {plan} plan ka bill {bill_amount} hai — {due_date} tak bhar dijiye.{notes_suffix}",
            "Ji {name} ji! {plan} account mein {bill_amount} baki hai, {due_date} se pehle bharein.{notes_suffix}",
            "{name} ji, {plan} bill {bill_amount} hai. {due_date} tak bharein.{notes_suffix}",
        ],
        "en-IN": [
            "{name}, your {plan} bill is {bill_amount}, due by {due_date}.{notes_suffix}",
            "Hi {name}! Your {plan} account has {bill_amount} due by {due_date}.{notes_suffix}",
            "{name}, {plan} bill amount is {bill_amount} — please pay by {due_date}.{notes_suffix}",
        ],
        "no_account": {
            "gu-IN": [
                "Chalo, bill check kari laiye. Tamaro 11-digit consumer number ke 10-digit registered mobile number kaiso?",
                "Ji! Bill jovaaa taaro consumer number ke registered mobile number daasho?",
                "Bill check karvaanu easy chhe — consumer number ke registered mobile number aapso?",
            ],
            "hi-IN": [
                "Haan, bill check karte hain. Aapka consumer number ya registered mobile number batayein?",
                "Ji bilkul! Consumer number ya mobile number bata dijiye, abhi dekh leti hoon.",
                "Sure! Consumer number ya registered mobile share karein, turant check karti hoon.",
            ],
            "en-IN": [
                "Sure, let me pull up your bill. Could you share your consumer number or registered mobile number?",
                "Happy to help! Just give me your consumer number or registered mobile.",
                "Got it — share your consumer number or registered mobile and I'll check right away.",
            ],
        },
    },
    "PAYMENT_HELP": {
        "gu-IN": [
            "Ji! Bill bharvano saulo raasto chhe mpay.guvnl.in. NEFT maate: UGVCLLTZ vatta 11-digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "Bilkul. mpay.guvnl.in par online bharo — saralas. Ya NEFT: UGVCLLTZ plus consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "Payment maate mpay.guvnl.in best chhe. NEFT karvanu hoy to: UGVCLLTZ vatta consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
        ],
        "hi-IN": [
            "Ji! Sabse aasaan tarika mpay.guvnl.in hai. NEFT ke liye: UGVCLLTZ aur 11-digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "Bilkul. mpay.guvnl.in par online kar lo — bahut simple. Ya NEFT: UGVCLLTZ plus consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "Payment ke liye mpay.guvnl.in use karein. NEFT: UGVCLLTZ plus consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
        ],
        "en-IN": [
            "Sure! Easiest way is mpay.guvnl.in — quick and simple. For NEFT: UGVCLLTZ plus 11-digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "You can pay at mpay.guvnl.in, it's straightforward. NEFT: UGVCLLTZ plus consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
            "Go to mpay.guvnl.in for online payment. Bank transfer: UGVCLLTZ plus consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
        ],
    },
    "POWER_OUTAGE": {
        "gu-IN": [
            "Light nathi aavti? Asuvidhaa badal maafi mangu chu. Me complaint nondhi lidhi chhe — aamari field team 2-4 kalak ma pohchi jashe.",
            "Oh, chinta na karo ji. Complaint register thai gai chhe. Aamaro team jaldi j avshe, andaze 2-4 kalak ma light aavi jashe.",
            "Aamne khabar thai gayu. Me tamari complaint nondhi lidhi chhe, aamari team 2-4 kalak ma supply restore kari deshe.",
        ],
        "hi-IN": [
            "Bijli nahi hai? Maafi chahti hoon. Complaint note kar li hai — hamaari field team 2-4 ghante mein aa jayegi.",
            "Ji, chinta mat karein. Complaint register ho gayi hai. Hamaara team 2-4 ghante mein pahunch jayega.",
            "Ho gaya note. Hamaari team nikal rahi hai, 2-4 ghante mein bijli aa jayegi.",
        ],
        "en-IN": [
            "Oh, I'm sorry about the power cut! I've logged your complaint — our field team should have it back on within 2 to 4 hours.",
            "I've noted the outage. Our team is on it and will restore supply within 2 to 4 hours.",
            "Sorry for the inconvenience! Complaint is registered. Power should be back within 2 to 4 hours.",
        ],
    },
    "SOLAR_BILLING": {
        "gu-IN": [
            "Solar billing simple chhe! Import units minus Export units — e tamaro net bill. Vadhu export hoy to June ma bank account ma credit maale.",
            "Ji, solar consumers nu bill net reading par aave — Import minus Export. June ma excess credit bank ma aave.",
            "Solar ma: Import units minus Export = tamaro bill. Dar varse June ma excess export amount bank account ma credit thay.",
        ],
        "hi-IN": [
            "Solar billing simple hai! Import minus Export units = net bill. Zyada export ho to June mein bank mein credit aata hai.",
            "Ji, solar walon ka bill net reading par — Import minus Export. June mein excess credit bank account mein milti hai.",
            "Solar mein: Import minus Export = aapka bill. Saal mein June mein excess export paisa bank mein aata hai.",
        ],
        "en-IN": [
            "Solar billing is simple! Import units minus Export units equals your bill. Any extra export gets credited to your bank every June.",
            "Net metering: Import minus Export equals your bill. Excess export is credited to your bank account annually in June.",
            "Your solar bill is Import minus Export units. Extra export credit comes to your bank every June.",
        ],
    },
    "SMART_METER": {
        "gu-IN": [
            "Oh, meter ma takleef chhe? Maafi mangu chu. Me complaint nondhi lidhi chhe — aamaro technician 2-3 working days ma tamane tyaat avshe.",
            "Chinta na karo ji, register kari lidhu chhe. Aamari technical team 2-3 working days ma pohchi jashe.",
            "Ho gayu note. Aamaro technician 2-3 working days ni andar aavi ne dekhi jashe.",
        ],
        "hi-IN": [
            "Arre, meter mein dikkat? Maafi chahti hoon. Complaint note kar li — technician 2-3 working days mein aa jayega.",
            "Ji, register kar liya. Chinta mat karein, hamaari technical team 2-3 working days mein pahunch jayegi.",
            "Ho gaya. Hamaara technician 2-3 working days ke andar aake dekh jayega.",
        ],
        "en-IN": [
            "Oh, smart meter trouble? Sorry about that! I've logged the complaint — our technician will be there within 2 to 3 working days.",
            "Got it, meter complaint is noted. Our technical team will visit within 2 to 3 working days.",
            "Done, complaint registered. Expect a technician within 2 to 3 working days.",
        ],
    },
    "RECONNECTION": {
        "gu-IN": [
            "Bill bharo ane 2-3 working days ma connection chalu thai jashe. Payment verify thai gaya baad team restore kari deshe.",
            "Ji, pending bill bharo ne — payment baad 2-3 working days ma line chalu thai jashe.",
            "Connection maate pending bill bharvun zaruri chhe. Bharso ane 2-3 working days ma supply aavi jashe.",
        ],
        "hi-IN": [
            "Pending bill bharein aur 2-3 working days mein connection chalu ho jayega.",
            "Ji, pending bill bharein — payment ke baad 2-3 working days mein bijli aa jayegi.",
            "Connection ke liye pending bill bharna hai. Bharein aur 2-3 working days mein supply restore hogi.",
        ],
        "en-IN": [
            "Clear the pending bill and we'll get you reconnected within 2 to 3 working days.",
            "Pay the pending bill and your connection will be back within 2 to 3 working days.",
            "Once the pending bill is paid, reconnection happens within 2 to 3 working days.",
        ],
        "personalized": {
            "gu-IN": [
                "Tamaro {bill_amount} no pending bill chhe. E bharo ane 2-3 working days ma connection restore thai jashe.",
                "{bill_amount} baki chhe. E bharo ne — 2-3 working days ma light aavi jashe.",
                "Bill {bill_amount} bharso to 2-3 working days ma connection chalu thai jashe.",
            ],
            "hi-IN": [
                "Aapka {bill_amount} pending bill hai. Bharein aur 2-3 working days mein reconnect ho jayega.",
                "{bill_amount} baki hai. Bharein — 2-3 working days mein bijli aa jayegi.",
                "Bill {bill_amount} bharein to 2-3 working days mein connection chalu ho jayega.",
            ],
            "en-IN": [
                "Your pending bill is {bill_amount}. Pay it and reconnection will happen within 2 to 3 working days.",
                "There's {bill_amount} pending. Clear that and you'll be reconnected within 2 to 3 working days.",
                "Pay {bill_amount} and connection restores within 2 to 3 working days.",
            ],
        },
    },
    "PREPAID": {
        "gu-IN": [
            "Lagey chhe balance zero thai gayu chhe, etle line bandh thai gai. mpay.guvnl.in par thi fatafat recharge karo — ane 3 percent rebate pan maale!",
            "Balance zero thay to supply auto-disconnect thay — evu j thayun chhe. Jaldi mpay.guvnl.in par recharge karo. 3 percent rebate bonus pan chhe.",
            "Ji, balance khatam thai gayu etle disconnect thayun. mpay.guvnl.in par recharge karo — 3 percent rebate pan maale.",
        ],
        "hi-IN": [
            "Lagta hai balance zero ho gaya, isliye supply cut hui. mpay.guvnl.in par jaldi recharge kar lo — 3 percent rebate bhi milta hai!",
            "Balance khatam hua to disconnect ho jaata hai — yahi hua. mpay.guvnl.in par recharge karo. 3 percent rebate ka fayda bhi uthao.",
            "Ji, balance zero se supply band hui. mpay.guvnl.in se recharge karo — 3 percent rebate bhi milegi.",
        ],
        "en-IN": [
            "Looks like your prepaid balance hit zero, which cut the supply. Recharge quickly at mpay.guvnl.in — you also get a 3 percent rebate!",
            "When prepaid balance goes to zero, supply stops automatically — that's what happened. Top it up at mpay.guvnl.in. 3 percent rebate too.",
            "Balance is zero so supply stopped. Recharge at mpay.guvnl.in to get back on — 3 percent rebate on charges.",
        ],
    },
    "NEW_CONNECTION": {
        "gu-IN": [
            "Navu connection joie chhe? Tamara nazdeek na SDN office par jaavo — Aadhaar, index copy, site plan saathe LT New Connection form bharo.",
            "Ji bilkul! SDN office par jaao, Aadhaar, index copy, site plan ready rakhjo ane LT New Connection form bharo.",
            "Chalo! SDN office par jaao — Aadhaar card, index copy, site plan saathe form bhari laao.",
        ],
        "hi-IN": [
            "Naya connection chahiye? Apne nzdik SDN office jayein — Aadhaar, index copy, site plan ke saath LT New Connection form bharein.",
            "Ji bilkul! SDN office mein jayein, Aadhaar, index copy, site plan le jao aur LT New Connection form bharein.",
            "Sure! SDN office jayein — Aadhaar card, index copy, site plan ready rakhein aur form bharein.",
        ],
        "en-IN": [
            "For a new connection, head to your nearest SDN office with Aadhaar card, index copy, and site plan to fill the LT New Connection form.",
            "Sure! Visit the SDN office with Aadhaar, index copy, and site plan — fill out the LT New Connection form.",
            "Go to your nearest SDN office with Aadhaar, index copy, and site plan and fill the LT New Connection form.",
        ],
    },
    "MOBILE_REG": {
        "gu-IN": [
            "Mobile register karvuu easy chhe! ugvcl.com par jaao — Consumer, Online Service, Link Mobile No. Consumer number naaakho, OTP verify karo, thai gayu.",
            "Ji, ugvcl.com kholjo. Consumer, Online Service, Link Mobile No. — consumer number daakho ane OTP thi verify karo.",
            "Simple chhe! ugvcl.com, Consumer, Online Service, Link Mobile No. — consumer number aapo ane OTP verify karo.",
        ],
        "hi-IN": [
            "Mobile register karna easy hai! ugvcl.com par jayein — Consumer, Online Service, Link Mobile No. Consumer number daalo, OTP verify karo, ho gaya.",
            "Ji, ugvcl.com kholein. Consumer, Online Service, Link Mobile No. — consumer number daalo aur OTP se verify karein.",
            "Simple hai! ugvcl.com, Consumer, Online Service, Link Mobile No. — consumer number daalein aur OTP verify karein.",
        ],
        "en-IN": [
            "Easy! Go to ugvcl.com, Consumer, Online Service, Link Mobile No. — enter consumer number, verify OTP, done.",
            "Visit ugvcl.com, go to Consumer, Online Service, Link Mobile No., enter consumer number and verify OTP.",
            "Simple — ugvcl.com, Consumer, Online Service, Link Mobile No., add consumer number, verify OTP, sorted.",
        ],
    },
    "HIGH_BILL": {
        "gu-IN": [
            "Bill zyada aavyo chhe? Samajhi shakay! Bill date thi 5 days ni andar, meter KWH reading ni photo, consumer number, Aadhaar ane bill copy saathe SDN office jaao — teo check kari aapshe.",
            "Arre, achanak motu bill aavyu? Chinta na karo. 5 days ni andar SDN office jaao — meter reading photo, Aadhaar, consumer number, bill copy laao. Sort out thai jashe.",
            "High bill? Me samjhu chu. Bill date thi 5 days andar SDN office ma jaavo — meter KWH photo, consumer number, Aadhaar, bill copy saathe.",
        ],
        "hi-IN": [
            "Bill zyada aaya? Bilkul samajh aata hai! Bill date se 5 din andar SDN office jayein — meter KWH reading photo, consumer number, Aadhaar aur bill copy le jaayein.",
            "Arre, achanak bada bill? Chinta mat. 5 din mein SDN office mein jaao — meter reading photo, Aadhaar, consumer number, bill copy. Sort ho jayega.",
            "High bill? Samajh aata hai. Bill date se 5 din ke andar SDN office jayein — meter KWH photo, Aadhaar, consumer number, bill copy saath.",
        ],
        "en-IN": [
            "I totally get why a sudden high bill is worrying. Visit the SDN office within 5 days — bring your meter KWH reading photo, Aadhaar, consumer number, and bill copy. They'll sort it out.",
            "That sounds stressful! SDN office within 5 days with meter reading photo, Aadhaar, consumer number, and bill copy — they'll look into it.",
            "High bill? Let's get it checked. SDN office within 5 days, meter KWH reading photo, Aadhaar, consumer number, and bill copy.",
        ],
    },
    "BILLING_FREQ": {
        "gu-IN": [
            "Smart meter waala ne monthly bill j aave — bi-monthly ke quarterly nu option nathi. Monthly tracking maate j aavun rakhe chhe.",
            "Ji, smart meter consumers ne monthly billing j hoy chhe. Anya option available nathi.",
            "Smart meter chhe to monthly bill j avshe. Bi-monthly ke quarterly nathi.",
        ],
        "hi-IN": [
            "Smart meter walon ko monthly bill hi milta hai — bi-monthly ya quarterly ka koi option nahi. Monthly tracking ke liye yahi better hai.",
            "Ji, smart meter users ke liye sirf monthly billing hoti hai. Koi aur option nahi hai.",
            "Smart meter hai to monthly bill hi aayega. Bi-monthly ya quarterly nahi.",
        ],
        "en-IN": [
            "Smart meter users get monthly bills only — no bi-monthly or quarterly option. Monthly is actually better for tracking usage.",
            "With a smart meter, billing is monthly only. There's no bi-monthly or quarterly option.",
            "Smart meter means monthly bills only — no other billing frequency available.",
        ],
    },
    "REFUND": {
        "gu-IN": [
            "Refund maate SDN office par jaao — application, payment receipt, bank statement ane Aadhaar card saathe. Amount original payment gateway par aavi jashe.",
            "Ji, refund process simple chhe. SDN office ma application, receipt, bank statement ane Aadhaar jama karo.",
            "Refund karvaa SDN office jaavo — application, receipt, bank statement, Aadhaar ready rakhjo.",
        ],
        "hi-IN": [
            "Refund ke liye SDN office jayein — application, payment receipt, bank statement aur Aadhaar ke saath. Amount original payment gateway par aayega.",
            "Ji, seedhi process hai. SDN office mein application, receipt, bank statement aur Aadhaar jama karein.",
            "SDN office mein jayein — refund application, receipt, bank statement, Aadhaar le jaayein.",
        ],
        "en-IN": [
            "For a refund, visit the SDN office with your application, payment receipt, bank statement, and Aadhaar. It'll be processed to the original payment gateway.",
            "Refund process is simple — SDN office with application, payment receipt, bank statement, and Aadhaar. Goes back to original payment method.",
            "Head to the SDN office with refund application, payment receipt, bank statement, and Aadhaar card.",
        ],
    },
    "NAME_ADDRESS": {
        "gu-IN": [
            "Name ke address badlavvaa SDN office par jaao — correction application, Aadhaar ane bill copy saathe. Verify thai gaya baad update thai jashe.",
            "Ji, SDN office par jaao — correction form, Aadhaar, bill copy saathe. Verification pachhi badlai jashe.",
            "Simple chhe! SDN office ma correction application, Aadhaar ane bill copy jama karo. Update thai jashe.",
        ],
        "hi-IN": [
            "Naam ya address badlwane ke liye SDN office jayein — correction application, Aadhaar aur bill copy saath. Verification ke baad update ho jayega.",
            "Ji, SDN office mein jayein — correction form, Aadhaar, bill copy saath le jaayein. Ho jayega.",
            "Simple hai! SDN office mein correction application, Aadhaar aur bill copy jama karein.",
        ],
        "en-IN": [
            "To update name or address, visit the SDN office with correction application, Aadhaar card, and bill copy. Updated after verification.",
            "Easy enough — SDN office with correction form, Aadhaar, and bill copy. They'll update it after verification.",
            "SDN office, correction application, Aadhaar, bill copy — all done after verification.",
        ],
    },
    "OFFICE_INFO": {
        "gu-IN": [
            "Tamara nazdeek nu SDN office Monday thi Saturday, subah 10:30 thi saanj 6 vage khulu chhe. Address maate ugvcl.com par Office Locator check karo.",
            "Ji, SDN office weekdays ane Saturday e 10:30 AM thi 6:00 PM khulu hoy chhe. ugvcl.com na Office Locator thi address malshe.",
            "SDN office Monday-Saturday, 10:30 AM thi 6 PM. ugvcl.com, Office Locator thi address jaano.",
        ],
        "hi-IN": [
            "Aapke nzdik ka SDN office Monday se Saturday, subah 10:30 se shaam 6 baje tak khula hai. Address ke liye ugvcl.com par Office Locator check karein.",
            "Ji, SDN office weekdays aur Saturday ko 10:30 AM se 6:00 PM tak khula rehta hai. ugvcl.com ke Office Locator se address dekh lo.",
            "SDN office Monday-Saturday, 10:30 AM se 6 PM. ugvcl.com, Office Locator se address jaanein.",
        ],
        "en-IN": [
            "Your nearest SDN office is open Monday to Saturday, 10:30 AM to 6:00 PM. Find the exact address on ugvcl.com under Office Locator.",
            "SDN offices work Monday through Saturday, 10:30 AM to 6 PM. Check ugvcl.com's Office Locator for the nearest one.",
            "Monday to Saturday, 10:30 AM to 6 PM — that's SDN office hours. Address on ugvcl.com, Office Locator.",
        ],
    },
    "COMPLAINT_NUMBER": {
        "gu-IN": [
            "UGVCL toll-free number chhe 19121 ke 1800-233-155-335 — 24 kalas available chhe. Online complaint maate ugvcl.com par Book Complaint section par jaavo.",
            "Ji, 19121 ke 1800-233-155-335 par call karo — 24 ghanta khula chhe. ugvcl.com, Book Complaint thi online pan kari shakay.",
            "Toll-free: 19121 ya 1800-233-155-335, 24x7 available. Online: ugvcl.com par Book Complaint.",
        ],
        "hi-IN": [
            "UGVCL toll-free: 19121 ya 1800-233-155-335 — 24 ghante available. Online complaint ke liye ugvcl.com par Book Complaint mein jayein.",
            "Ji, 19121 ya 1800-233-155-335 par call karein — 24 ghante available. ugvcl.com, Book Complaint se online bhi kar sakte ho.",
            "Toll-free: 19121 ya 1800-233-155-335, 24x7. Online: ugvcl.com par Book Complaint.",
        ],
        "en-IN": [
            "UGVCL toll-free numbers are 19121 or 1800-233-155-335 — available 24 hours. For online complaints, go to Book Complaint on ugvcl.com.",
            "Call 19121 or 1800-233-155-335 anytime — 24-hour helpline. Or log it online at ugvcl.com under Book Complaint.",
            "Toll-free: 19121 or 1800-233-155-335, 24/7. Online: ugvcl.com, Book Complaint section.",
        ],
    },
}

# ---------------------------------------------------------------------------
# Empathy prefixes — varied, natural, not template-like
# ---------------------------------------------------------------------------
_EMPATHY_PREFIX: dict[str, dict[str, list[str]]] = {
    "POWER_OUTAGE": {
        "gu-IN": ["Asuvidhaa badal maafi mangu chu. ", "Oh, chinta na karo ji. ", "Me samjhu chu, takleef chhe. "],
        "hi-IN": ["Takleef ke liye maafi chahti hoon. ", "Ji, chinta mat karein. ", "Samajh aata hai, pareshani ho rahi hai. "],
        "en-IN": ["I'm so sorry about this. ", "That must be frustrating — let me help. ", "Sorry for the trouble! "],
    },
    "HIGH_BILL": {
        "gu-IN": ["Tamari chinta bilkul samjay chhe. ", "Arre, achanak motu bill! Me samjhu chu. ", "Ji, e joine aachraj thay — samjhu chu. "],
        "hi-IN": ["Aapki chinta bilkul samajh aati hai. ", "Arre, achanak bada bill! Samajh aata hai. ", "Ji, yeh dekhke hairani hoti hai — samajh aata hai. "],
        "en-IN": ["I totally get why this is worrying. ", "A sudden high bill is always alarming — I understand. ", "That's understandably concerning. "],
    },
    "SMART_METER": {
        "gu-IN": ["Takleef aavi, maafi mangu chu. ", "Oh, meter ma issue chhe — chinta na karo. ", "Me samjhu chu, e aagadhu hoy chhe. "],
        "hi-IN": ["Pareshani ho rahi hai, maafi chahti hoon. ", "Meter mein issue — chinta mat karein. ", "Samajh aata hai, yeh bura lagta hai. "],
        "en-IN": ["Sorry you're dealing with this. ", "Meter issues are annoying — let me sort this. ", "I understand, that's frustrating. "],
    },
    "RECONNECTION": {
        "gu-IN": ["Chinta na karo, hun madad karishu. ", "Ji, connection restore karvaani koshish karishu. ", "Me samjhu chu, e important chhe. "],
        "hi-IN": ["Chinta mat karein, main madad karungi. ", "Ji, connection restore karne ki koshish karenge. ", "Samajh aata hai, yeh zaroori hai. "],
        "en-IN": ["Don't worry, we'll sort this out. ", "I'll help get your connection restored. ", "Understood — let's get that fixed. "],
    },
    "REFUND": {
        "gu-IN": ["Chinta samjay chhe, hun check karishu. ", "Ji, paise parat malva joie — me madad karishu. ", "Me samjhu chu, e important chhe. "],
        "hi-IN": ["Aapki chinta samajh aati hai. ", "Ji, paisa wapas milna chahiye — main madad karungi. ", "Samajh aata hai, yeh important hai. "],
        "en-IN": ["I understand your concern about this. ", "You deserve that refund — let me help. ", "Totally get it — let's sort this out. "],
    },
}

_FRUSTRATED_PREFIX: dict[str, list[str]] = {
    "gu-IN": [
        "Maafi mangu chu, tamari frustration bilkul valid chhe. ",
        "Ji, me samjhu chu — aa situation frustrating chhe. ",
        "Bilkul samjay chhe, e situation ma koi pan frustrated thay. Maafi mangu chu. ",
    ],
    "hi-IN": [
        "Maafi chahti hoon, aapki pareshani bilkul sahi hai. ",
        "Ji, samajh aata hai — yeh situation frustrating hai. ",
        "Bilkul samajh aata hai, aise mein koi bhi pareshan ho jaata. Maafi chahti hoon. ",
    ],
    "en-IN": [
        "I sincerely apologize for the trouble. I completely understand your frustration. ",
        "I'm really sorry you're going through this — your frustration is completely valid. ",
        "That sounds really frustrating, and I'm sorry. Let me help fix this right away. ",
    ],
}

# ---------------------------------------------------------------------------
# FSM messages — varied where repeated often
# ---------------------------------------------------------------------------
_FSM_MSGS: dict[str, dict | list] = {
    "ask_consumer_number": {
        "gu-IN": [
            "Chalo, bill check kari laiye. Tamaro consumer number ke registered mobile number kaiso?",
            "Ji! Tamaro 11-digit consumer number ke 10-digit registered mobile number daasho?",
            "Sure — consumer number ke registered mobile number aapso to hun turant check kari chu.",
        ],
        "hi-IN": [
            "Haan, check karte hain. Aapka consumer number ya registered mobile number batayein?",
            "Ji! 11-digit consumer number ya 10-digit registered mobile number bata dijiye.",
            "Sure — consumer number ya registered mobile share karein, abhi dekh leti hoon.",
        ],
        "en-IN": [
            "Sure, let me check that. Could you share your consumer number or registered mobile?",
            "Happy to help! Your consumer number or registered mobile number please?",
            "Got it — share your consumer number or registered mobile and I'll check right away.",
        ],
    },
    "ask_more_digits": {
        "gu-IN": [
            "Baaki no number aap bolsho, hun sambhalu chu.",
            "Ji, agal chhalao — baaki digits bolsho.",
            "Sure, hun sambhalu chu — baaki number bolsho.",
        ],
        "hi-IN": [
            "Baaki number bataiye, main sun rahi hoon.",
            "Ji, aage bataiye — baaki digits bolein.",
            "Sure, sun rahi hoon — baaki number bolein.",
        ],
        "en-IN": [
            "Please go ahead with the remaining digits, I'm listening.",
            "Got it so far — please continue with the rest.",
            "Sure, I'm listening — please share the remaining digits.",
        ],
    },
    "account_not_found_retry": {
        "gu-IN": "Khed chhe, account maylyu nahi. Tamaro 10-digit mobile ke 11-digit consumer number ek vaar aapo.",
        "hi-IN": "Maafi chahti hoon, account nahi mila. Aapka 10-digit mobile ya 11-digit consumer number ek baar dijiye.",
        "en-IN": "I'm sorry, couldn't find the account. Please try your 10-digit mobile or 11-digit consumer number once more.",
    },
    "continue_without": {
        "gu-IN": "Koi vakhat nahi ji, account verify nahi thayun. Tamari problem janaavo, hun madad karishu.",
        "hi-IN": "Koi baat nahi ji, account verify nahi hua. Aapki samasya batayein, main madad karungi.",
        "en-IN": "No worries, couldn't verify the account. Tell me how I can help you.",
    },
    "escalate": {
        "gu-IN": "Ji, tamari request aamaari system ma note thayi chhe. Aamaari team 2 kalak ma tamane contact karashe. UGVCL ma call karavaa baadal aabhar.",
        "hi-IN": "Ji, aapki request hamare system mein note ho gayi. Hamari team 2 ghante mein aapko contact karegi. UGVCL mein call karne ka shukriya.",
        "en-IN": "Your request has been noted. Our team will get back to you within 2 hours. Thank you for calling UGVCL.",
    },
    "closing": {
        "gu-IN": " UGVCL ma call karavaa baadal aabhar. Khyal rakhjo!",
        "hi-IN": " UGVCL mein call karne ka shukriya. Apna khayal rakhein!",
        "en-IN": " Thank you for calling UGVCL. Take care!",
    },
    "follow_up": {
        "gu-IN": [" Aapni koi biji jarur chhe?", " Baaki koi sawaal?", " Haju koi madad joie chhe?"],
        "hi-IN": [" Aur koi seva karu?", " Kuch aur poochna hai?", " Aur koi kaam ho to batao."],
        "en-IN": [" Anything else I can help with?", " Is there anything else?", " Need help with anything else?"],
    },
    "identified": {
        "gu-IN": [
            "{name} ji, tamaro {plan} account maylyo! Shu madad joie tamne?",
            "Ji {name} ji! {plan} account ready chhe. Shu kari shakhu tamara maate?",
            "Maylyu {name} ji! {plan} account found. Shu seva kari shakhu?",
        ],
        "hi-IN": [
            "{name} ji, aapka {plan} account mil gaya! Kya madad chahiye aapko?",
            "Ji {name} ji! {plan} account ready hai. Kya kar sakti hoon aapke liye?",
            "Mil gaya {name} ji! {plan} account found. Kya seva kar sakti hoon?",
        ],
        "en-IN": [
            "Found it, {name}! Your {plan} account is up. How can I help you today?",
            "Hi {name}! Got your {plan} account here. What can I do for you?",
            "Got it, {name}! {plan} account is ready. How may I assist you?",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _pick(options):
    """Return a random item if list, else the value as-is."""
    if isinstance(options, list):
        return random.choice(options)
    return options


def classify_intent(text: str) -> tuple[str, int]:
    """Return (intent_name, keyword_match_count). UNKNOWN if nothing matches."""
    lower = text.lower()
    best_intent = "UNKNOWN"
    best_count = 0
    for intent_name, keywords in _INTENT_KEYWORDS:
        count = sum(1 for kw in keywords if kw.lower() in lower)
        if count > best_count:
            best_count = count
            best_intent = intent_name
    return best_intent, best_count


def t(key: str, lang: str, **fmt) -> str:
    """Return a (possibly random) FSM message string."""
    entry = _FSM_MSGS.get(key, {})
    if isinstance(entry, dict):
        options = entry.get(lang) or entry.get("en-IN") or key
    else:
        options = entry
    text = _pick(options)
    return text.format(**fmt) if fmt else text


_TICKET_SUFFIX: dict[str, str] = {
    "gu-IN": " Tamari complaint number chhe {ticket_id} — e yaad rakhsho.",
    "hi-IN": " Aapki complaint number hai {ticket_id} — yeh yaad rakhein.",
    "en-IN": " Your complaint number is {ticket_id} — please note it down.",
}

_TICKET_INTENTS = {"POWER_OUTAGE", "SMART_METER", "HIGH_BILL"}


def build_reply(
    intent: str,
    consumer: dict | None,
    lang: str,
    frustrated: bool = False,
    ticket_id: str | None = None,
) -> str:
    """Build the spoken reply for a given intent, with randomised conversational phrasing."""
    # Reply templates already have empathy embedded — only add prefix for frustrated callers
    prefix = _pick(_FRUSTRATED_PREFIX.get(lang, "")) if frustrated else ""

    template = _REPLIES.get(intent)
    if template is None:
        return prefix + t("escalate", lang)

    # BILL_INFO — personalised if account known
    if intent == "BILL_INFO":
        if consumer:
            notes = consumer.get("notes", "") or ""
            notes_suffix = ""
            if "overdue" in notes.lower() or "disconnection" in notes.lower():
                _suf = {
                    "gu-IN": " Jaldi bharo — disconnection risk chhe.",
                    "hi-IN": " Jaldi bharein — disconnection ka khatra hai.",
                    "en-IN": " Please pay urgently to avoid disconnection.",
                }
                notes_suffix = _suf.get(lang, "")
            elif "prepaid" in notes.lower():
                _suf = {
                    "gu-IN": " Prepaid account — mpay.guvnl.in par balance check karo.",
                    "hi-IN": " Prepaid account — mpay.guvnl.in par balance check karein.",
                    "en-IN": " Prepaid account — check balance at mpay.guvnl.in.",
                }
                notes_suffix = _suf.get(lang, "")
            tmpl = _pick(template.get(lang) or template.get("en-IN", ""))
            return prefix + tmpl.format(
                name=consumer.get("name", ""),
                plan=consumer.get("plan", ""),
                bill_amount=consumer.get("bill_amount", ""),
                due_date=consumer.get("due_date", ""),
                notes_suffix=notes_suffix,
            )
        else:
            no_acc = template.get("no_account", {})
            return prefix + _pick(no_acc.get(lang) or no_acc.get("en-IN", "Please share your consumer number."))

    # RECONNECTION — personalised bill amount if known
    if intent == "RECONNECTION" and consumer:
        personalized = template.get("personalized", {})
        tmpl = _pick(personalized.get(lang) or personalized.get("en-IN"))
        if tmpl:
            return prefix + tmpl.format(bill_amount=consumer.get("bill_amount", ""))

    # All other intents
    reply = _pick(template.get(lang) or template.get("en-IN", ""))
    base = prefix + reply

    # Append ticket number for complaint intents when a ticket was raised
    if ticket_id and intent in _TICKET_INTENTS:
        suffix_tmpl = _TICKET_SUFFIX.get(lang, _TICKET_SUFFIX["en-IN"])
        base += suffix_tmpl.format(ticket_id=ticket_id)

    return base
