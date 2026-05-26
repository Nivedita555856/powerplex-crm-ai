-- ============================================================
-- AppliServe AI CRM — Supabase PostgreSQL Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. CUSTOMERS
CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,          -- e.g. CUST001
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    phone         TEXT,
    city          TEXT,
    segment       TEXT CHECK (segment IN ('Premium','Standard','Basic')),
    since         DATE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 2. APPLIANCES
CREATE TABLE IF NOT EXISTS appliances (
    appliance_id  TEXT PRIMARY KEY,          -- e.g. APPL001
    brand         TEXT NOT NULL,
    model         TEXT NOT NULL,
    category      TEXT,                      -- AC, Refrigerator, etc.
    type_code     TEXT,
    price         NUMERIC(10,2),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TECHNICIANS
CREATE TABLE IF NOT EXISTS technicians (
    technician_id TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    specialization TEXT,
    city          TEXT,
    phone         TEXT,
    rating        NUMERIC(3,2),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 4. WARRANTY DATA
CREATE TABLE IF NOT EXISTS warranty_data (
    warranty_id     TEXT PRIMARY KEY,
    customer_id     TEXT REFERENCES customers(customer_id),
    appliance_id    TEXT REFERENCES appliances(appliance_id),
    serial_number   TEXT,
    purchase_date   DATE,
    expiry_date     DATE,
    status          TEXT CHECK (status IN ('Active','Expired')),
    purchase_amount NUMERIC(10,2),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 5. TICKETS
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id    TEXT PRIMARY KEY,
    customer_id  TEXT REFERENCES customers(customer_id),
    appliance_id TEXT REFERENCES appliances(appliance_id),
    warranty_id  TEXT REFERENCES warranty_data(warranty_id),
    issue        TEXT NOT NULL,
    priority     TEXT CHECK (priority IN ('critical','high','medium','low')),
    status       TEXT CHECK (status IN ('Open','In Progress','Resolved','Closed')),
    created_date DATE DEFAULT CURRENT_DATE,
    assigned_to  TEXT REFERENCES technicians(technician_id),
    resolution   TEXT,
    source       TEXT DEFAULT 'manual',      -- manual | n8n | make | api
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 6. SALES LEADS
CREATE TABLE IF NOT EXISTS sales_leads (
    lead_id      TEXT PRIMARY KEY,
    name         TEXT,
    email        TEXT,
    phone        TEXT,
    product      TEXT,
    stage        TEXT,                       -- Prospect, Qualified, Proposal, Won, Lost
    value        NUMERIC(10,2),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 7. EMAILS
CREATE TABLE IF NOT EXISTS emails (
    email_id     TEXT PRIMARY KEY,
    customer_id  TEXT REFERENCES customers(customer_id),
    subject      TEXT,
    body         TEXT,
    direction    TEXT CHECK (direction IN ('inbound','outbound')),
    sent_date    DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 8. REVIEWS
CREATE TABLE IF NOT EXISTS reviews (
    review_id    TEXT PRIMARY KEY,
    customer_id  TEXT REFERENCES customers(customer_id),
    appliance_id TEXT REFERENCES appliances(appliance_id),
    rating       INT CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT,
    review_date  DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 9. APPROVAL QUEUE (Human-in-the-loop)
CREATE TABLE IF NOT EXISTS approval_queue (
    approval_id  TEXT PRIMARY KEY,
    item_type    TEXT,                       -- refund | warranty_override | escalation
    description  TEXT,
    amount       NUMERIC(10,2),
    customer_id  TEXT REFERENCES customers(customer_id),
    status       TEXT DEFAULT 'pending'      CHECK (status IN ('pending','approved','rejected')),
    decided_by   TEXT,
    decided_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes for common queries ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tickets_customer    ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status      ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority    ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_warranty_customer   ON warranty_data(customer_id);
CREATE INDEX IF NOT EXISTS idx_warranty_status     ON warranty_data(status);
CREATE INDEX IF NOT EXISTS idx_emails_customer     ON emails(customer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_customer    ON reviews(customer_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage         ON sales_leads(stage);

-- ── Row Level Security (enable after testing) ───────────────────────────────
-- ALTER TABLE customers       ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tickets         ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE warranty_data   ENABLE ROW LEVEL SECURITY;

-- ── Helper view: open tickets with customer + appliance detail ───────────────
CREATE OR REPLACE VIEW open_tickets_view AS
    SELECT
        t.ticket_id, t.issue, t.priority, t.status, t.created_date, t.source,
        c.name      AS customer_name, c.city, c.segment,
        a.brand     AS appliance_brand, a.model AS appliance_model, a.category
    FROM tickets t
    JOIN customers  c ON c.customer_id  = t.customer_id
    LEFT JOIN appliances a ON a.appliance_id = t.appliance_id
    WHERE t.status IN ('Open','In Progress')
    ORDER BY
        CASE t.priority
            WHEN 'critical' THEN 0
            WHEN 'high'     THEN 1
            WHEN 'medium'   THEN 2
            WHEN 'low'      THEN 3 END,
        t.created_date DESC;

-- ── Helper view: active warranties ──────────────────────────────────────────
CREATE OR REPLACE VIEW active_warranties_view AS
    SELECT
        w.warranty_id, w.serial_number, w.purchase_date, w.expiry_date,
        w.purchase_amount,
        c.name      AS customer_name, c.email, c.city,
        a.brand, a.model, a.category
    FROM warranty_data w
    JOIN customers  c ON c.customer_id  = w.customer_id
    JOIN appliances a ON a.appliance_id = w.appliance_id
    WHERE w.status = 'Active'
    ORDER BY w.expiry_date;
