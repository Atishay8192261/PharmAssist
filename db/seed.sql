-- PharmAssist seed data
-- Safe to re-run: truncates and resets identities

BEGIN;

TRUNCATE TABLE
  Order_Items,
  Orders,
  Users,
  Pricing_Rules,
  Inventory_Batches,
  Product_SKUs,
  Products,
  Customers
RESTART IDENTITY CASCADE;

-- 1) Customers
INSERT INTO Customers(name, address, customer_type) VALUES
  ('PharmEasy Pharmacy', '123 Market St, Springfield', 'Pharmacy'),
  ('City Hospital', '456 Health Ave, Springfield', 'Hospital');

-- 2) Products
INSERT INTO Products(name, manufacturer, description) VALUES
  ('Paracetamol', 'GSK', 'Analgesic and antipyretic'),
  ('Amoxicillin', 'Acme Labs', 'Broad-spectrum antibiotic');

-- 3) Product SKUs
-- Resolve product ids by name to avoid assuming serials
INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price)
SELECT p.product_id, '500mg 10-strip', 'tablet', 1.50
FROM Products p WHERE p.name = 'Paracetamol';

INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price)
SELECT p.product_id, '650mg 15-strip', 'tablet', 2.00
FROM Products p WHERE p.name = 'Paracetamol';

INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price)
SELECT p.product_id, '250mg 100-bottle', 'capsule', 0.80
FROM Products p WHERE p.name = 'Amoxicillin';

-- 4) Inventory Batches
-- Paracetamol 500mg batches (two batches with different expiries)
INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
SELECT s.sku_id, 'P500-A1', DATE '2027-01-01', 100, 0.90
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
WHERE p.name = 'Paracetamol' AND s.package_size = '500mg 10-strip' AND s.unit_type = 'tablet';

INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
SELECT s.sku_id, 'P500-A2', DATE '2026-06-01', 50, 0.85
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
WHERE p.name = 'Paracetamol' AND s.package_size = '500mg 10-strip' AND s.unit_type = 'tablet';

-- Paracetamol 650mg
INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
SELECT s.sku_id, 'P650-B1', DATE '2027-03-01', 75, 1.20
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
WHERE p.name = 'Paracetamol' AND s.package_size = '650mg 15-strip' AND s.unit_type = 'tablet';

-- Amoxicillin 250mg
INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
SELECT s.sku_id, 'AMOX-C1', DATE '2026-12-15', 200, 0.50
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
WHERE p.name = 'Amoxicillin' AND s.package_size = '250mg 100-bottle' AND s.unit_type = 'capsule';

-- 5) Pricing Rules
-- 10% off Paracetamol 500mg for PharmEasy on orders >= 10 units
INSERT INTO Pricing_Rules(sku_id, customer_id, min_quantity, discount_percentage)
SELECT s.sku_id, c.customer_id, 10, 10.00
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
JOIN Customers c ON c.name = 'PharmEasy Pharmacy'
WHERE p.name = 'Paracetamol' AND s.package_size = '500mg 10-strip' AND s.unit_type = 'tablet';

-- 5% off customer-wide for City Hospital on orders >= 20 units (any SKU)
INSERT INTO Pricing_Rules(sku_id, customer_id, min_quantity, discount_percentage)
SELECT NULL, c.customer_id, 20, 5.00
FROM Customers c WHERE c.name = 'City Hospital';

-- 12% off SKU-wide for Paracetamol 650mg on orders >= 30 units (any customer)
INSERT INTO Pricing_Rules(sku_id, customer_id, min_quantity, discount_percentage)
SELECT s.sku_id, NULL, 30, 12.00
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
WHERE p.name = 'Paracetamol' AND s.package_size = '650mg 15-strip' AND s.unit_type = 'tablet';

-- 6) Users (Note: password_hash values here are placeholders for development)
-- You can replace with real bcrypt hashes later.
INSERT INTO Users(customer_id, username, password_hash, role)
SELECT NULL, 'admin', 'password123', 'admin';

INSERT INTO Users(customer_id, username, password_hash, role)
SELECT c.customer_id, 'pharma1', 'password123', 'customer'
FROM Customers c WHERE c.name = 'PharmEasy Pharmacy';

INSERT INTO Users(customer_id, username, password_hash, role)
SELECT c.customer_id, 'hosp1', 'password123', 'customer'
FROM Customers c WHERE c.name = 'City Hospital';

COMMIT;
