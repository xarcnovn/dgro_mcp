import sqlite3
from datetime import datetime

# Create database with test data
conn = sqlite3.connect('case_search.db')
cursor = conn.cursor()

# Enable foreign keys
cursor.execute("PRAGMA foreign_keys=ON")

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL,
    phone TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('new', 'in_progress', 'vendor_search', 'negotiation', 'completed')),
    category TEXT NOT NULL,
    details TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK(urgency IN ('low', 'medium', 'high')),
    budget_range TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    results_json TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    vendor_email TEXT NOT NULL,
    price_quoted REAL,
    details TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'rejected')),
    received_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS email_communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    vendor_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('sent', 'received')),
    timestamp TEXT NOT NULL,
    thread_id TEXT,
    FOREIGN KEY (case_id) REFERENCES cases(id)
)
""")

# Insert test data
now = datetime.now().isoformat()

# Insert test user
cursor.execute("""
INSERT INTO users (name, email, company, phone)
VALUES ('John Doe', 'john@example.com', 'Example Corp', '+1234567890')
""")
user_id = cursor.lastrowid

# Insert test cases
cursor.execute("""
INSERT INTO cases (user_id, status, category, details, urgency, budget_range, created_at, updated_at)
VALUES (?, 'vendor_search', 'Office Supplies', 'Need 50 ergonomic chairs for new office', 'high', '$10,000 - $15,000', ?, ?)
""", (user_id, now, now))
case_id_1 = cursor.lastrowid

cursor.execute("""
INSERT INTO cases (user_id, status, category, details, urgency, budget_range, created_at, updated_at)
VALUES (?, 'in_progress', 'IT Equipment', 'Need 20 laptops for new employees', 'medium', '$20,000 - $30,000', ?, ?)
""", (user_id, now, now))
case_id_2 = cursor.lastrowid

cursor.execute("""
INSERT INTO cases (user_id, status, category, details, urgency, created_at, updated_at)
VALUES (?, 'completed', 'Cleaning Services', 'Monthly office cleaning service', 'low', ?, ?)
""", (user_id, now, now))
case_id_3 = cursor.lastrowid

# Insert test searches
cursor.execute("""
INSERT INTO searches (case_id, query, timestamp, results_json)
VALUES (?, 'ergonomic office chairs bulk purchase', ?, '[]')
""", (case_id_1, now))

cursor.execute("""
INSERT INTO searches (case_id, query, timestamp, results_json)
VALUES (?, 'business laptops bulk purchase', ?, '[]')
""", (case_id_2, now))

# Insert test offers
cursor.execute("""
INSERT INTO offers (case_id, vendor_email, price_quoted, details, status, received_at)
VALUES (?, 'vendor1@chairs.com', 12500.00, 'Herman Miller Aeron chairs, 50 units', 'pending', ?)
""", (case_id_1, now))

cursor.execute("""
INSERT INTO offers (case_id, vendor_email, price_quoted, details, status, received_at)
VALUES (?, 'vendor2@chairs.com', 11000.00, 'Steelcase Leap chairs, 50 units', 'pending', ?)
""", (case_id_1, now))

cursor.execute("""
INSERT INTO offers (case_id, vendor_email, price_quoted, details, status, received_at)
VALUES (?, 'vendor@laptops.com', 25000.00, 'Dell Latitude 5540, 20 units', 'accepted', ?)
""", (case_id_2, now))

# Insert test email communications
cursor.execute("""
INSERT INTO email_communications (case_id, vendor_email, subject, body, direction, timestamp, thread_id)
VALUES (?, 'vendor1@chairs.com', 'Quote Request for Office Chairs', 'Hello, we need 50 ergonomic chairs...', 'sent', ?, 'thread_1')
""", (case_id_1, now))

cursor.execute("""
INSERT INTO email_communications (case_id, vendor_email, subject, body, direction, timestamp, thread_id)
VALUES (?, 'vendor1@chairs.com', 'RE: Quote Request for Office Chairs', 'Thank you for your inquiry. Here is our quote...', 'received', ?, 'thread_1')
""", (case_id_1, now))

conn.commit()
conn.close()

print("Test database created successfully with sample data!")
print(f"- 1 user")
print(f"- 3 cases")
print(f"- 2 searches")
print(f"- 3 offers")
print(f"- 2 email communications")
