"""
Intent classifier and reply builder for UGVCL voice agent.
Supports Gujarati, Hindi, and English keyword matching.
"""

# (keywords, intent_name)
# Keywords match against lowercase user text (Gujarati script + romanised + English)
_INTENT_KEYWORDS: list[tuple[list[str], str]] = [
    ("BILL_INFO", [
        "bill ketu", "bill ketlu", "bill amount", "bill info", "bill jovu",
        "bill janavvu", "maru bill", "aapmnu bill", "bill che ketlu",
        "bill kyare", "current bill", "mane bill", "bill baki",
        "bill kiti", "bill kem", "maro bill",
        "outstanding", "arrear", "pending amount", "due amount",
        # Gujarati script + short catchall
        "બિલ", "bill કેટ", "bill બાકી", "મારું bill", "bill kem",
        "bill baaki", "baaki bill", "bill aavyo", "bill aavshhe",
        # Hindi
        "mera bill", "bill kitna", "bill batao", "baaki bill", "baki kitna",
        "बिल", "बिल कितना", "बकाया",
        # English
        "my bill", "bill amount", "how much bill", "current bill",
        "outstanding bill", "pending bill",
    ]),
    ("PAYMENT_HELP", [
        "bill bharvo", "payment", "bharvu", "online pay", "neft", "mpay",
        "bill kevi rite", "kevi rite bharvo", "payment link", "pay kari",
        "payment karvo", "online bharo", "kyan bharvo", "payment method",
        "virtual account", "bank of baroda", "ifsc",
        # Gujarati script
        "ચૂકવ", "ભરવ", "ભુગ", "mpay", "ઓનલાઇન pay",
        # Hindi
        "bill kaise bharein", "payment kaise", "online payment",
        "भुगतान", "पेमेंट",
        # English
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
        # Hindi
        "bijli nahi", "light nahi", "power nahi", "bijli gayi",
        "transformer jal", "line tut", "bijli fault",
        # English
        "no power", "power outage", "electricity gone", "no electricity",
        "transformer burnt", "transformer fault", "line down",
    ]),
    ("SOLAR_BILLING", [
        "solar", "solar bill", "solar meter", "net meter",
        "import unit", "export unit", "solar system",
        "solar nu bill", "solarnu bill", "solar export",
        "solar generate", "rooftop solar", "solar panel",
        # Hindi
        "solar ka bill",
        # English
        "solar billing", "solar calculation", "net metering",
    ]),
    ("SMART_METER", [
        "smart meter", "meter issue", "app open nathi", "ugvcl app",
        "meter reading", "smart meter complaint", "meter rite chalto nathi",
        "meter kaam nathi", "meter chal nathi",
        "મીટર ખરાબ", "smart meter ખરાબ", "smart meter app", "મીટર",
        # Hindi
        "मीटर", "स्मार्ट मीटर",
        # English
        "smart meter problem", "meter not working", "meter complaint",
    ]),
    ("RECONNECTION", [
        "reconnect", "connection cut", "light aavse kyare", "kyare aavse",
        "bill bharya pachi", "supply restore", "connection restore",
        "disconnect thayo", "supply bai", "connection bai",
        "ક્યારે આવશે", "light ક્યારે", "reconnection",
        # Hindi
        "connection kab aayega", "bijli kab aayegi",
        # English
        "when will power come", "reconnect service",
    ]),
    ("PREPAID", [
        "prepaid balance", "balance zero", "balance check", "recharge",
        "prepaid meter", "prepaid", "balance ketu", "balance ketlu",
        "recharge kevi rite", "balance janavvu", "balance",
        "પ્રીપેઇડ", "recharge link",
        # English
        "prepaid recharge", "check balance", "prepaid account",
    ]),
    ("NEW_CONNECTION", [
        "new connection", "navu connection", "navu jodavo", "apply connection",
        "navi line", "connection levun", "connection apply",
        "નવું connection", "connection aapvo",
        # Hindi
        "naya connection", "connection chahiye",
        # English
        "new electricity connection", "apply for connection",
    ]),
    ("MOBILE_REG", [
        "mobile register", "mobile number", "link mobile", "mobile link",
        "number register", "sms nathi aavti", "sms alert",
        "otp nathi aavtu", "otp nahi", "otp not", "otp",
        "mobile nondh",
        "mobile નોંધ", "number update",
        # English
        "register mobile", "update mobile number", "mobile sms",
    ]),
    ("HIGH_BILL", [
        "bill vadhu", "bill vadhare", "reading khothi", "reading ghalat",
        "meter reading", "bill correct", "high bill", "bill vadu",
        "reading wrong", "bill motu", "reading verify",
        "bill ઘણું", "ઊંચો bill", "bill vadharo",
        # Hindi
        "bill bahut zyada", "galat reading",
        # English
        "wrong reading", "disputed bill", "meter reading wrong",
    ]),
    ("BILLING_FREQ", [
        "quarterly billing", "bi-monthly", "billing interval",
        "monthly ни jagae", "monthly ni jagye", "billing change",
        "quarterly", "2 mahine nu bill", "monthly billing badlavu",
        "billing monthly", "quarterly karvun",
        # English
        "change billing frequency", "quarterly bill", "bimonthly",
    ]),
    ("REFUND", [
        "refund", "paise pachi", "return paise", "refund kevi",
        "paise parat", "amount return", "refund apply",
        # Hindi
        "paisa wapas", "refund chahiye",
        # English
        "get refund", "money back", "refund process",
    ]),
    ("NAME_ADDRESS", [
        "name change", "naam badlav", "naam khothu", "address change",
        "address khothi", "naam correct", "address correct",
        "naam update", "address update",
        "નામ ખોટ", "address ખોટ",
        # English
        "wrong name", "name correction", "address change",
    ]),
    ("OFFICE_INFO", [
        "sdn office", "office kyat", "office time", "office kya",
        "office address", "office javu", "office info",
        "SDN", "ઓફિસ", "office hours",
        # English
        "office location", "where is office", "office timing",
    ]),
    ("COMPLAINT_NUMBER", [
        "toll free", "complaint number", "helpline", "19121",
        "customer care number", "contact number",
        "ફરિયાદ ક્યાં", "complaint kyat",
        # English
        "helpline number", "complaint contact",
    ]),
]

# Multilingual static replies for each intent
_REPLIES: dict[str, dict[str, str]] = {
    "BILL_INFO": {
        "gu-IN": "{name}, aaapnu {plan} nu bill {bill_amount} chhe, {due_date} sudhi bharvo.{notes_suffix}",
        "hi-IN": "{name}, aapka {plan} bill {bill_amount} hai, {due_date} tak bharein.{notes_suffix}",
        "en-IN": "{name}, your {plan} bill is {bill_amount}, due by {due_date}.{notes_suffix}",
        "no_account": {
            "gu-IN": "Bill jaanvaa tmaaro consumer number athva registered mobile number apo.",
            "hi-IN": "Bill jaanne ke liye apna consumer number ya registered mobile number dijiye.",
            "en-IN": "Please provide your consumer number or registered mobile number to check your bill.",
        },
    },
    "PAYMENT_HELP": {
        "gu-IN": "Bill payment mpay.guvnl.in upar online karo. NEFT: UGVCLLTZ vatta 11 digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
        "hi-IN": "Bill payment mpay.guvnl.in par karein. NEFT: UGVCLLTZ aur 11 digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.",
        "en-IN": "Pay your bill at mpay.guvnl.in. For NEFT: UGVCLLTZ plus 11-digit consumer number at Bank of Baroda, IFSC BARB0ALKAPU.",
    },
    "POWER_OUTAGE": {
        "gu-IN": "Tmaari power outage complaint aamaari system ma register thayi chhe. Aamaro field team investigate karshe, 2-4 kalas ma supply restore thase.",
        "hi-IN": "Aapki power outage complaint hamare system mein register ho gayi hai. Hamara field team investigate karega, 2-4 ghante mein supply restore hogi.",
        "en-IN": "Your power outage complaint is registered in our system. Our field team will investigate and restore supply within 2-4 hours.",
    },
    "SOLAR_BILLING": {
        "gu-IN": "Solar consumer no bill Import units minus Export units net reading upar aave. Excess export amount dar varse June maah ma bank account ma credit thay.",
        "hi-IN": "Solar ka bill Import units minus Export units net reading par aata hai. Excess export amount saal mein June mein bank account mein credit hoti hai.",
        "en-IN": "Solar bill is calculated on Import units minus Export units. Excess export amount is credited to your bank annually in June.",
    },
    "SMART_METER": {
        "gu-IN": "Tmaaro smart meter complaint aamaari system ma register thayi chhe. Aamaro technical team 2-3 working days ma visit karshe.",
        "hi-IN": "Aapka smart meter complaint hamare system mein register ho gaya hai. Hamara technical team 2-3 working days mein visit karega.",
        "en-IN": "Your smart meter complaint is registered in our system. Our technical team will visit within 2-3 working days.",
    },
    "RECONNECTION": {
        "gu-IN": "Pending bill bharo, payment verify thai gaya bad 2-3 working days ma reconnection thai jashe.",
        "hi-IN": "Pending bill bharein, payment verify hone ke 2-3 working days mein reconnection ho jayegi.",
        "en-IN": "Pay your pending bill; reconnection will happen within 2-3 working days after payment.",
        "personalized": {
            "gu-IN": "Pending bill {bill_amount} bharo, 2-3 working days ma reconnection thai jashe.",
            "hi-IN": "Pending bill {bill_amount} bharein, 2-3 working days mein reconnection ho jayegi.",
            "en-IN": "Pay your pending bill of {bill_amount}; reconnection within 2-3 working days.",
        },
    },
    "PREPAID": {
        "gu-IN": "Prepaid balance zero thay tyare supply disconnect thay. mpay.guvnl.in upar recharge karo. Prepaid consumers ne energy charge upar 3 percent rebate benefit.",
        "hi-IN": "Prepaid balance zero hone par supply disconnect ho jata hai. mpay.guvnl.in par recharge karein. 3 percent rebate ka fayda milta hai.",
        "en-IN": "Prepaid balance zero disconnects supply. Recharge at mpay.guvnl.in. Prepaid consumers get 3 percent rebate on energy charges.",
    },
    "NEW_CONNECTION": {
        "gu-IN": "UGVCL SDN office ma LT New Connection Application form bharo. Aadhaar card, index copy, site plan saathe apply karo.",
        "hi-IN": "UGVCL SDN office mein LT New Connection Application form bharein. Aadhaar card, index copy, site plan saath laayein.",
        "en-IN": "Visit UGVCL SDN office with LT New Connection Application form, Aadhaar card, index copy, and site plan.",
    },
    "MOBILE_REG": {
        "gu-IN": "ugvcl.com upar Consumer, Online Service, Link Mobile No. ma consumer number enter kari OTP verify kari mobile register karo.",
        "hi-IN": "ugvcl.com par Consumer, Online Service, Link Mobile No. mein consumer number aur OTP se mobile register karein.",
        "en-IN": "Visit ugvcl.com, go to Consumer, Online Service, Link Mobile No., enter consumer number and verify OTP.",
    },
    "HIGH_BILL": {
        "gu-IN": "Bill date na 5 days ni andar meter KWH reading ni photo sathe consumer number, Aadhaar card, bill copy SDN office ma submit karo.",
        "hi-IN": "Bill date ke 5 din ke andar meter KWH reading ki photo, consumer number, Aadhaar card, bill copy SDN office mein jama karein.",
        "en-IN": "Within 5 days of bill date, submit meter KWH reading photo, consumer number, Aadhaar card, and bill copy at SDN office.",
    },
    "BILLING_FREQ": {
        "gu-IN": "Smart meter consumers ne monthly billing mandatory chhe. Bi-monthly athva quarterly billing ni provision nathi.",
        "hi-IN": "Smart meter consumers ke liye monthly billing mandatory hai. Bi-monthly ya quarterly billing ka koi provision nahi.",
        "en-IN": "Smart meter consumers receive monthly bills. There is no provision for bi-monthly or quarterly billing.",
    },
    "REFUND": {
        "gu-IN": "SDN office ma refund application, payment receipt, bank statement ne Aadhaar card saathe submit karo. Refund original payment gateway upar process thase.",
        "hi-IN": "SDN office mein refund application, payment receipt, bank statement aur Aadhaar card jama karein.",
        "en-IN": "Submit refund application, payment receipt, bank statement, and Aadhaar card at SDN office. Refund processed to original payment gateway.",
    },
    "NAME_ADDRESS": {
        "gu-IN": "SDN office ma name athva address correction application, Aadhaar card ne bill copy submit karo. Verification pachhi update.",
        "hi-IN": "SDN office mein name ya address correction application, Aadhaar card aur bill copy jama karein.",
        "en-IN": "Submit name or address correction application, Aadhaar card, and bill copy at SDN office.",
    },
    "OFFICE_INFO": {
        "gu-IN": "Nearest UGVCL SDN office Monday to Saturday, 10:30 AM thi 6:00 PM khuli chhe. ugvcl.com upar Office Locator ma address malshe.",
        "hi-IN": "Nearest UGVCL SDN office Monday to Saturday, 10:30 AM se 6:00 PM tak khuli hai. ugvcl.com par Office Locator mein address milega.",
        "en-IN": "Your nearest UGVCL SDN office is open Monday to Saturday, 10:30 AM to 6:00 PM. Find the address on ugvcl.com Office Locator.",
    },
    "COMPLAINT_NUMBER": {
        "gu-IN": "UGVCL toll-free number 19121 athva 1800-233-155-335 chhe, 24 kalas available. Online complaint ugvcl.com upar Book Complaint section ma.",
        "hi-IN": "UGVCL toll-free number 19121 ya 1800-233-155-335, 24 ghante available. Online: ugvcl.com par Book Complaint.",
        "en-IN": "UGVCL toll-free: 19121 or 1800-233-155-335, available 24 hours. Online: ugvcl.com Book Complaint section.",
    },
}

_EMPATHY_PREFIX: dict[str, dict[str, str]] = {
    "POWER_OUTAGE": {
        "gu-IN": "Asuvidhaa baadal khed chhe. ",
        "hi-IN": "Pareshani ke liye khed hai. ",
        "en-IN": "I'm sorry for the inconvenience. ",
    },
    "HIGH_BILL": {
        "gu-IN": "Aapni bill baabat ni chinta samjay chhe. ",
        "hi-IN": "Bill ki chinta samajh mein aati hai. ",
        "en-IN": "I understand your concern about the bill. ",
    },
    "SMART_METER": {
        "gu-IN": "Meter ni problem sunaai, jaldi hal karshu. ",
        "hi-IN": "Meter ki samasya samajh aaya, jaldi hal karein. ",
        "en-IN": "I understand you're having meter issues. ",
    },
    "RECONNECTION": {
        "gu-IN": "Connection baabat chinta na karo. ",
        "hi-IN": "Connection ke baare mein chinta mat karein. ",
        "en-IN": "Don't worry, we'll get your connection restored. ",
    },
    "REFUND": {
        "gu-IN": "Paise parat karavva baabat samjay chhe. ",
        "hi-IN": "Paise wapas ke baare mein samajh aata hai. ",
        "en-IN": "I understand you're waiting for a refund. ",
    },
}

_FRUSTRATED_PREFIX: dict[str, str] = {
    "gu-IN": "Huh samjhyo, tamari frustration bilkul valid chhe. ",
    "hi-IN": "Main samajhta hoon, aapki frustration bilkul sahi hai. ",
    "en-IN": "I completely understand your frustration. ",
}

_FSM_MSGS: dict[str, dict[str, str]] = {
    "ask_consumer_number": {
        "gu-IN": "કૃપા કરી તમારો consumer number અથવા registered mobile number આપો.",
        "hi-IN": "कृपया अपना consumer number या registered mobile number दीजिए।",
        "en-IN": "Please provide your consumer number or registered mobile number.",
    },
    "ask_more_digits": {
        "gu-IN": "બાકીનો નંબર બોલો, સાંભળી રહ્યો છું.",
        "hi-IN": "बाकी नंबर बोलिए, सुन रहा हूं।",
        "en-IN": "Please continue with the remaining digits.",
    },
    "account_not_found_retry": {
        "gu-IN": "Account મળ્યું નહીં. 10-digit mobile number અથવા 11-digit consumer number ફરી આપો.",
        "hi-IN": "Account नहीं मिला। 10-digit mobile number या 11-digit consumer number फिर दीजिए।",
        "en-IN": "Account not found. Please provide your 10-digit mobile or 11-digit consumer number.",
    },
    "continue_without": {
        "gu-IN": "Account verify ન થઈ શક્યું. તમારી સમસ્યા જણાવો, મદદ કરીશ.",
        "hi-IN": "Account verify नहीं हुआ। अपनी समस्या बताइए, मदद करूंगा।",
        "en-IN": "Could not verify account. Please tell me how I can help you.",
    },
    "escalate": {
        "gu-IN": "Tmaari request aamaari system ma note thayi chhe. Aamaro specialist team 2 kalas ma sampark karshe. UGVCL call karvaano aabhar.",
        "hi-IN": "Aapki request hamare system mein note ho gayi hai. Hamari specialist team 2 ghante mein sampark karegi. UGVCL mein call karne ka shukriya.",
        "en-IN": "Your request has been noted in our system. Our specialist team will contact you within 2 hours. Thank you for calling UGVCL.",
    },
    "closing": {
        "gu-IN": " UGVCL call કરવા બદલ આભાર.",
        "hi-IN": " UGVCL में call करने के लिए शुक्रिया।",
        "en-IN": " Thank you for calling UGVCL.",
    },
    "follow_up": {
        "gu-IN": " Baaki koi sawaal chhe?",
        "hi-IN": " Aur koi sawaal?",
        "en-IN": " Is there anything else I can help you with?",
    },
    "identified": {
        "gu-IN": "{name}, તમારો {plan} account મળ્યો. શું help જોઈએ?",
        "hi-IN": "{name}, आपका {plan} account मिला। कैसे help करें?",
        "en-IN": "{name}, found your {plan} account. How can I help you?",
    },
}


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
    """Return translated FSM message string."""
    entry = _FSM_MSGS.get(key, {})
    text = entry.get(lang) or entry.get("en-IN") or key
    return text.format(**fmt) if fmt else text


def build_reply(intent: str, consumer: dict | None, lang: str, frustrated: bool = False) -> str:
    """Build the spoken reply for a given intent, optionally personalised with consumer data."""
    if frustrated:
        prefix = _FRUSTRATED_PREFIX.get(lang, "")
    else:
        prefix = _EMPATHY_PREFIX.get(intent, {}).get(lang, "")

    template = _REPLIES.get(intent)
    if template is None:
        return prefix + t("escalate", lang)

    # BILL_INFO — personalized if account known
    if intent == "BILL_INFO":
        if consumer:
            notes = consumer.get("notes", "") or ""
            notes_suffix = ""
            if "overdue" in notes.lower() or "disconnection" in notes.lower():
                _suf = {"gu-IN": " Jaldi bharvo, disconnection risk chhe.", "hi-IN": " Jaldi bharein, disconnection ka khatra hai.", "en-IN": " Please pay urgently to avoid disconnection."}
                notes_suffix = _suf.get(lang, "")
            elif "prepaid" in notes.lower():
                _suf = {"gu-IN": " Prepaid account — mpay.guvnl.in upar balance check karo.", "hi-IN": " Prepaid account — mpay.guvnl.in par balance check karein.", "en-IN": " Prepaid account — check balance at mpay.guvnl.in."}
                notes_suffix = _suf.get(lang, "")
            tmpl = template.get(lang) or template.get("en-IN", "")
            return prefix + tmpl.format(
                name=consumer.get("name", ""),
                plan=consumer.get("plan", ""),
                bill_amount=consumer.get("bill_amount", ""),
                due_date=consumer.get("due_date", ""),
                notes_suffix=notes_suffix,
            )
        else:
            no_acc = template.get("no_account", {})
            return prefix + (no_acc.get(lang) or no_acc.get("en-IN", "Please provide consumer number."))

    # RECONNECTION — personalized bill amount if known
    if intent == "RECONNECTION" and consumer:
        personalized = template.get("personalized", {})
        tmpl = personalized.get(lang) or personalized.get("en-IN")
        if tmpl:
            return prefix + tmpl.format(bill_amount=consumer.get("bill_amount", ""))

    # All other intents — static reply
    reply = template.get(lang) or template.get("en-IN", "")
    return prefix + reply
