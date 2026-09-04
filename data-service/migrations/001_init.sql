CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,
    available INTEGER NOT NULL CHECK (available >= 0),
    warehouse TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO orders(order_id, customer_id, product_id, quantity, status)
VALUES
    ('ord-001', 'cust-001', 'keyboard', 1, 'confirmed'),
    ('ord-002', 'cust-002', 'mouse', 2, 'confirmed'),
    ('ord-003', 'cust-003', 'monitor', 1, 'processing'),
    ('ord-1001', 'cust-1001', 'keyboard', 1, 'confirmed')
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO inventory(product_id, available, warehouse)
VALUES
    ('keyboard', 42, 'bogota-01'),
    ('mouse', 88, 'bogota-01'),
    ('monitor', 17, 'medellin-01')
ON CONFLICT (product_id) DO NOTHING;
