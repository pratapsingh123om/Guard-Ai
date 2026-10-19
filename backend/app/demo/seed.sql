PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    organization TEXT NOT NULL,
    region TEXT NOT NULL,
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high'))
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TEXT NOT NULL
);

INSERT INTO customers (id, organization, region, risk_tier) VALUES
    (1, 'Northstar Labs', 'APAC', 'low'),
    (2, 'Contoso Research', 'EU', 'medium'),
    (3, 'Fabrikam Systems', 'US', 'high');

INSERT INTO orders (id, customer_id, status, total_cents, created_at) VALUES
    (1001, 1, 'completed', 129900, '2026-09-14T10:30:00Z'),
    (1002, 1, 'processing', 45900, '2026-10-02T08:15:00Z'),
    (1003, 2, 'completed', 87500, '2026-10-05T12:45:00Z'),
    (1004, 3, 'review', 250000, '2026-10-11T17:20:00Z');
