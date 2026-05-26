"""
generate_data.py — Lightweight sample data for Appliance CRM
Reduced counts for fast processing on free-tier services.

Counts:
  customers: 20
  appliances: 10
  technicians: 5
  warranty_records: 30
  tickets: 40
  sales_leads: 15
  emails: 20
  reviews: 20
  chat_history: 30
"""

import csv, json, random, os
from datetime import datetime, timedelta

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── helpers ───────────────────────────────────────────────────────────────────
def rand_date(start_days_ago=365, end_days_ago=0):
    d = datetime.today() - timedelta(days=random.randint(end_days_ago, start_days_ago))
    return d.strftime("%Y-%m-%d")

def rand_phone():
    return f"+91-9{random.randint(100,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

def write_csv(filename, rows, fieldnames):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓ {filename} ({len(rows)} rows)")

# ── 1. CUSTOMERS (20) ─────────────────────────────────────────────────────────
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata", "Ahmedabad"]
FIRST  = ["Arun","Priya","Rahul","Sneha","Vikram","Meera","Arjun","Divya","Suresh","Anita",
           "Ravi","Kavya","Sanjay","Pooja","Nikhil","Asha","Deepak","Rekha","Ajay","Nisha"]
LAST   = ["Kumar","Sharma","Patel","Reddy","Iyer","Singh","Nair","Joshi","Verma","Gupta",
           "Rao","Mehta","Shah","Das","Pillai","Agarwal","Bose","Mishra","Thakur","Kapoor"]

customers = []
for i in range(1, 21):
    fn, ln = FIRST[i-1], LAST[i-1]
    city = random.choice(CITIES)
    customers.append({
        "customer_id": f"CUST{i:03d}",
        "name": f"{fn} {ln}",
        "email": f"{fn.lower()}.{ln.lower()}@email.com",
        "phone": rand_phone(),
        "city": city,
        "since": rand_date(730, 30),
        "segment": random.choice(["Premium","Standard","Basic"]),
    })

write_csv("customers.csv", customers,
    ["customer_id","name","email","phone","city","since","segment"])

# ── 2. APPLIANCES (10) ────────────────────────────────────────────────────────
APPLIANCES = [
    ("APPL001","Air Conditioner","CoolBreeze","CB-1.5T","1.5 Ton Split AC",32000,"AC"),
    ("APPL002","Air Conditioner","CoolBreeze","CB-2T","2 Ton Split AC",42000,"AC"),
    ("APPL003","Refrigerator","FrostKing","FK-260L","260L Frost-Free",22000,"Fridge"),
    ("APPL004","Refrigerator","FrostKing","FK-340L","340L Frost-Free",31000,"Fridge"),
    ("APPL005","Washing Machine","WashPro","WP-6.5F","6.5kg Front Load",28000,"WM"),
    ("APPL006","Washing Machine","WashPro","WP-7.5T","7.5kg Top Load",18000,"WM"),
    ("APPL007","Microwave","MicroChef","MC-20S","20L Solo Microwave",6000,"MW"),
    ("APPL008","Microwave","MicroChef","MC-28C","28L Convection",11000,"MW"),
    ("APPL009","TV","VisionX","VX-43S","43\" 4K Smart TV",35000,"TV"),
    ("APPL010","TV","VisionX","VX-55S","55\" 4K QLED TV",55000,"TV"),
]

appliance_rows = []
for row in APPLIANCES:
    appliance_rows.append({
        "appliance_id": row[0], "category": row[1], "brand": row[2],
        "model": row[3], "description": row[4], "price": row[5], "type_code": row[6],
        "warranty_years": random.choice([1,2]),
    })

write_csv("appliances.csv", appliance_rows,
    ["appliance_id","category","brand","model","description","price","type_code","warranty_years"])

# ── 3. TECHNICIANS (5) ────────────────────────────────────────────────────────
TECH_NAMES = ["Ramesh Kumar","Sunil Sharma","Ajit Verma","Pradeep Nair","Kishore Patel"]
SPECIALIZATIONS = [["AC","WM"],["Fridge","MW"],["AC","TV"],["WM","Fridge"],["TV","MW","AC"]]

technicians = []
for i, name in enumerate(TECH_NAMES, 1):
    technicians.append({
        "technician_id": f"TECH{i:02d}",
        "name": name,
        "phone": rand_phone(),
        "specialization": "|".join(SPECIALIZATIONS[i-1]),
        "city": random.choice(CITIES),
        "rating": round(random.uniform(3.5, 5.0), 1),
        "active_tickets": random.randint(0, 5),
    })

write_csv("technicians.csv", technicians,
    ["technician_id","name","phone","specialization","city","rating","active_tickets"])

# ── 4. WARRANTY RECORDS (30) ──────────────────────────────────────────────────
warranty_rows = []
appl_ids = [a[0] for a in APPLIANCES]
for i in range(1, 31):
    cust = random.choice(customers)
    appl_id = random.choice(appl_ids)
    appl = next(a for a in appliance_rows if a["appliance_id"] == appl_id)
    purchase = rand_date(500, 10)
    purchase_dt = datetime.strptime(purchase, "%Y-%m-%d")
    expiry_dt = purchase_dt + timedelta(days=365 * appl["warranty_years"])
    warranty_rows.append({
        "warranty_id": f"WRN{i:03d}",
        "customer_id": cust["customer_id"],
        "appliance_id": appl_id,
        "purchase_date": purchase,
        "expiry_date": expiry_dt.strftime("%Y-%m-%d"),
        "status": "Active" if expiry_dt > datetime.today() else "Expired",
        "serial_number": f"SN{random.randint(100000,999999)}",
        "purchase_amount": appl["price"],
    })

write_csv("warranty_data.csv", warranty_rows,
    ["warranty_id","customer_id","appliance_id","purchase_date","expiry_date",
     "status","serial_number","purchase_amount"])

# ── 5. TICKETS (40) ───────────────────────────────────────────────────────────
ISSUES = {
    "AC":    ["Not cooling properly","Water dripping from indoor unit","Remote not working",
               "Strange noise from outdoor unit","AC not turning on"],
    "Fridge":["Not cooling","Ice maker not working","Door seal damaged",
               "Unusual noise","Temperature fluctuating"],
    "WM":    ["Not spinning","Water leaking","Error code E2","Drum not rotating","Clothes not clean"],
    "MW":    ["Not heating","Turntable not rotating","Door not closing","Sparking inside","Display issue"],
    "TV":    ["No picture","Sound issue","WiFi not connecting","Remote not pairing","Screen flickering"],
}
STATUSES = ["Open","In Progress","Resolved","Closed"]
STATUS_W  = [0.25, 0.35, 0.25, 0.15]
PRIORITIES= ["Low","Medium","High","Critical"]

tickets = []
for i in range(1, 41):
    wrn = random.choice(warranty_rows)
    appl = next(a for a in appliance_rows if a["appliance_id"] == wrn["appliance_id"])
    tc = appl["type_code"]
    issue = random.choice(ISSUES.get(tc, ["General issue"]))
    status = random.choices(STATUSES, STATUS_W)[0]
    created = rand_date(180, 0)
    tech = random.choice(technicians) if status != "Open" else None
    tickets.append({
        "ticket_id": f"TKT{i:04d}",
        "customer_id": wrn["customer_id"],
        "warranty_id": wrn["warranty_id"],
        "appliance_id": wrn["appliance_id"],
        "issue": issue,
        "status": status,
        "priority": random.choice(PRIORITIES),
        "created_date": created,
        "resolved_date": rand_date(30, 0) if status in ["Resolved","Closed"] else "",
        "technician_id": tech["technician_id"] if tech else "",
        "resolution_notes": f"Issue resolved: {issue.lower()} fixed." if status in ["Resolved","Closed"] else "",
        "satisfaction_score": random.randint(3, 5) if status in ["Resolved","Closed"] else "",
    })

write_csv("tickets.csv", tickets,
    ["ticket_id","customer_id","warranty_id","appliance_id","issue","status","priority",
     "created_date","resolved_date","technician_id","resolution_notes","satisfaction_score"])

# ── 6. SALES LEADS (15) ───────────────────────────────────────────────────────
LEAD_SOURCES = ["Website","Referral","Social Media","Trade Show","Inbound Call"]
LEAD_STAGES  = ["New","Contacted","Qualified","Proposal Sent","Negotiation","Closed Won","Closed Lost"]
LEAD_NAMES   = ["Manoj Tiwari","Sunita Agarwal","Karan Malhotra","Lakshmi Rao","Amit Bhatia",
                 "Swati Desai","Rajesh Nayak","Preeti Choudhary","Vinod Sinha","Nalini Menon",
                 "Harsh Pandey","Usha Trivedi","Sameer Qureshi","Geeta Bhatt","Dinesh Yadav"]

leads = []
for i, name in enumerate(LEAD_NAMES, 1):
    appl = random.choice(appliance_rows)
    stage = random.choice(LEAD_STAGES)
    leads.append({
        "lead_id": f"LEAD{i:03d}",
        "name": name,
        "email": f"{name.split()[0].lower()}@prospect.com",
        "phone": rand_phone(),
        "city": random.choice(CITIES),
        "interested_product": appl["model"],
        "category": appl["category"],
        "estimated_value": appl["price"],
        "stage": stage,
        "source": random.choice(LEAD_SOURCES),
        "created_date": rand_date(90, 0),
        "last_contact": rand_date(30, 0),
        "notes": f"Interested in {appl['category']}. Budget ~₹{appl['price']:,}.",
    })

write_csv("sales_leads.csv", leads,
    ["lead_id","name","email","phone","city","interested_product","category",
     "estimated_value","stage","source","created_date","last_contact","notes"])

# ── 7. EMAILS (20) ────────────────────────────────────────────────────────────
EMAIL_SUBJECTS = [
    "Your service request has been received",
    "Technician visit scheduled for tomorrow",
    "Your appliance warranty is expiring soon",
    "Service completed — please share your feedback",
    "Exclusive offer on extended warranty",
    "Annual maintenance reminder",
    "Follow-up: Unresolved complaint",
    "Invoice for repair service",
    "Thank you for your purchase",
    "New product available — upgrade offer",
]

emails = []
for i in range(1, 21):
    cust = random.choice(customers)
    ticket = random.choice(tickets) if random.random() > 0.4 else None
    emails.append({
        "email_id": f"EMAIL{i:03d}",
        "customer_id": cust["customer_id"],
        "ticket_id": ticket["ticket_id"] if ticket else "",
        "direction": random.choice(["Outbound","Inbound"]),
        "subject": random.choice(EMAIL_SUBJECTS),
        "body_snippet": f"Dear {cust['name'].split()[0]}, we are writing regarding your recent service request.",
        "sent_date": rand_date(90, 0),
        "status": random.choice(["Sent","Delivered","Read","Replied"]),
    })

write_csv("emails.csv", emails,
    ["email_id","customer_id","ticket_id","direction","subject","body_snippet","sent_date","status"])

# ── 8. REVIEWS (20) ───────────────────────────────────────────────────────────
REVIEW_TEMPLATES = [
    ("Excellent service! Technician was very professional and fixed the issue quickly.", 5),
    ("Good experience overall. Took a bit longer than expected but resolved.", 4),
    ("Average service. Technician was late but issue was fixed.", 3),
    ("Poor response time. Had to call multiple times to get a technician.", 2),
    ("Very happy with the service. Would recommend to others.", 5),
    ("The issue was fixed but technician left the area messy.", 3),
    ("Outstanding! Fixed within 2 hours of complaint. Highly satisfied.", 5),
    ("Disappointing experience. Had to reschedule twice.", 2),
    ("Decent service, nothing exceptional. Issue resolved.", 3),
    ("Superb! Technician explained the issue clearly and fixed it on first visit.", 5),
]

reviews = []
for i in range(1, 21):
    cust = random.choice(customers)
    ticket = random.choice([t for t in tickets if t["status"] in ["Resolved","Closed"]] or tickets)
    template = random.choice(REVIEW_TEMPLATES)
    reviews.append({
        "review_id": f"REV{i:03d}",
        "customer_id": cust["customer_id"],
        "ticket_id": ticket["ticket_id"],
        "rating": template[1],
        "review_text": template[0],
        "review_date": rand_date(60, 0),
        "sentiment": "Positive" if template[1] >= 4 else ("Neutral" if template[1] == 3 else "Negative"),
        "category": random.choice(["Service Speed","Technician Quality","Issue Resolution","Communication"]),
    })

write_csv("reviews.csv", reviews,
    ["review_id","customer_id","ticket_id","rating","review_text","review_date","sentiment","category"])

# ── 9. CHAT HISTORY (30) ─────────────────────────────────────────────────────
CHAT_SAMPLES = [
    ("How do I check my warranty status?", "You can check your warranty status by providing your serial number or purchase date. Would you like me to look it up?"),
    ("My AC is not cooling properly.", "I'm sorry to hear that. When did you first notice the issue? Is there any unusual sound or water dripping?"),
    ("I want to book a service for my refrigerator.", "Sure! I can help you schedule a service visit. Can you share your registered phone number and the issue you're facing?"),
    ("The technician didn't show up for the appointment.", "I apologize for the inconvenience. I'm escalating this to our service team right away. You'll receive a call within 2 hours."),
    ("Is my washing machine still under warranty?", "Let me check. Could you provide your warranty ID or the serial number of your machine?"),
    ("How long will the repair take?", "Most repairs are completed within 1–3 working days depending on spare part availability."),
    ("I'm not satisfied with the service quality.", "I'm very sorry to hear that. Your feedback is important. I'm connecting you with our customer care team for a follow-up."),
    ("What is covered under the warranty?", "The warranty covers manufacturing defects and component failures. It does not cover physical damage, pest damage, or power surge damage."),
    ("Can I extend my warranty?", "Yes! We offer 1-year and 2-year extended warranty plans. Would you like me to send you the pricing details?"),
    ("My TV screen is flickering after 6 months of purchase.", "Flickering can be due to a loose HDMI connection or a display issue. Since you're within warranty, I'll raise a service ticket for you."),
]

chats = []
for i in range(1, 31):
    cust = random.choice(customers)
    sample = CHAT_SAMPLES[(i-1) % len(CHAT_SAMPLES)]
    chats.append({
        "chat_id": f"CHAT{i:03d}",
        "customer_id": cust["customer_id"],
        "timestamp": (datetime.today() - timedelta(days=random.randint(0, 60),
                                                    hours=random.randint(0, 23))).strftime("%Y-%m-%dT%H:%M:00"),
        "user_message": sample[0],
        "bot_response": sample[1],
        "intent": random.choice(["warranty_check","service_booking","complaint","general_query","escalation"]),
        "resolved": random.choice([True, False]),
    })

path = os.path.join(DATA_DIR, "chat_history.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(chats, f, indent=2)
print(f"  ✓ chat_history.json (30 records)")

print("\n✅ All data files generated successfully in /data/")
