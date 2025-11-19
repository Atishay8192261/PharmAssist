-- PharmAssist Schema (PostgreSQL / Neon compatible)

-- 1. Customers (Pharmacies, Hospitals)
CREATE TABLE IF NOT EXISTS Customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    customer_type VARCHAR(50) -- e.g., 'Pharmacy', 'Hospital'
);

-- 2. Products (The general drug, e.g., "Paracetamol")
CREATE TABLE IF NOT EXISTS Products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255),
    description TEXT
);

-- 3. Product SKUs (A specific version of a product, e.g., "Paracetamol 500mg 10-strip")
CREATE TABLE IF NOT EXISTS Product_SKUs (
    sku_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES Products(product_id),
    package_size VARCHAR(100), -- e.g., '10-strip', '100-bottle'
    unit_type VARCHAR(50), -- e.g., 'tablet', 'vial'
    base_price NUMERIC(10, 2) NOT NULL CHECK (base_price >= 0)
);

-- 4. Inventory Batches (The actual, physical stock)
CREATE TABLE IF NOT EXISTS Inventory_Batches (
    batch_id SERIAL PRIMARY KEY,
    sku_id INT NOT NULL REFERENCES Product_SKUs(sku_id),
    batch_no VARCHAR(100) NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_on_hand INT NOT NULL CHECK (quantity_on_hand >= 0),
    cost_price NUMERIC(10, 2) NOT NULL CHECK (cost_price >= 0),
    -- A single SKU can have multiple batches, but a batch number should be unique for a given SKU
    UNIQUE(sku_id, batch_no)
);

-- 5. Users (For app login - Admins or Customers)
CREATE TABLE IF NOT EXISTS Users (
    user_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES Customers(customer_id), -- NULL for Admins
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'customer'))
);

-- 6. Orders
CREATE TABLE IF NOT EXISTS Orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES Customers(customer_id),
    order_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'shipped', 'cancelled'))
);

-- 7. Order Items (Links an Order to a specific BATCH)
-- This is a critical design choice. We sell from a batch, not a SKU.
CREATE TABLE IF NOT EXISTS Order_Items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES Orders(order_id),
    batch_id INT NOT NULL REFERENCES Inventory_Batches(batch_id),
    quantity_ordered INT NOT NULL CHECK (quantity_ordered > 0),
    -- The price for this item at the time of sale
    sale_price NUMERIC(10, 2) NOT NULL
);

-- 8. Pricing Rules (For customer-specific discounts)
CREATE TABLE IF NOT EXISTS Pricing_Rules (
    rule_id SERIAL PRIMARY KEY,
    sku_id INT REFERENCES Product_SKUs(sku_id), -- NULLable for customer-wide discount
    customer_id INT REFERENCES Customers(customer_id), -- NULLable for SKU-wide discount
    min_quantity INT DEFAULT 1,
    discount_percentage NUMERIC(5, 2) CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
    -- Rule priority can be added later if needed
    UNIQUE(sku_id, customer_id, min_quantity)
);

-- 10. Shopping Cart (one active cart per user for simplicity)
CREATE TABLE IF NOT EXISTS Carts (
    cart_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- 11. Cart Items
CREATE TABLE IF NOT EXISTS Cart_Items (
    cart_item_id SERIAL PRIMARY KEY,
    cart_id INT NOT NULL REFERENCES Carts(cart_id) ON DELETE CASCADE,
    sku_id INT NOT NULL REFERENCES Product_SKUs(sku_id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    UNIQUE(cart_id, sku_id)
);

CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON Cart_Items(cart_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_sku_id ON Cart_Items(sku_id);

-- 9. Create Indexes for Optimization
CREATE INDEX IF NOT EXISTS idx_batches_sku_id ON Inventory_Batches(sku_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry_date ON Inventory_Batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON Orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON Order_Items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_batch_id ON Order_Items(batch_id);
