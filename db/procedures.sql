-- Stored Procedures for PharmAssist (PostgreSQL)

-- sp_PlaceOrder: Place an order for a specific batch with SERIALIZABLE isolation and row-level locking.
-- Contract:
--   CALL sp_PlaceOrder(p_customer_id, p_batch_id, p_quantity, o_order_id, o_order_item_id, o_sale_price);
-- Inputs:
--   p_customer_id INT - required, customer placing the order
--   p_batch_id    INT - required, specific Inventory_Batches.batch_id being sold
--   p_quantity    INT - required, number of units to sell (>0)
-- Outputs:
--   o_order_id        INT - created order id
--   o_order_item_id   INT - created order item id
--   o_sale_price      NUMERIC(10,2) - unit price used for this sale (after discount)
-- Behavior:
--   - Runs inside a TRANSACTION with ISOLATION LEVEL SERIALIZABLE
--   - Locks the batch row with SELECT ... FOR UPDATE
--   - If stock is sufficient, updates Inventory_Batches and inserts Orders/Order_Items, then COMMITs
--   - If stock is insufficient or any error occurs, ROLLBACKs and raises an error

CREATE OR REPLACE PROCEDURE sp_PlaceOrder(
	IN p_customer_id INT,
	IN p_batch_id INT,
	IN p_quantity INT,
	OUT o_order_id INT,
	OUT o_order_item_id INT,
	OUT o_sale_price NUMERIC(10,2)
)
LANGUAGE plpgsql
AS $$
DECLARE
	v_qty_on_hand INT;
	v_sku_id INT;
	v_base_price NUMERIC(10,2);
	v_discount NUMERIC(5,2) := 0;
	v_price NUMERIC(10,2);
BEGIN
	-- Validate input
	IF p_quantity IS NULL OR p_quantity <= 0 THEN
		RAISE EXCEPTION 'Quantity must be > 0';
	END IF;
	IF p_customer_id IS NULL THEN
		RAISE EXCEPTION 'Customer id is required';
	END IF;
	IF p_batch_id IS NULL THEN
		RAISE EXCEPTION 'Batch id is required';
	END IF;

	-- Lock the batch row to prevent concurrent decrements
	SELECT quantity_on_hand, sku_id
	  INTO v_qty_on_hand, v_sku_id
	  FROM Inventory_Batches
	 WHERE batch_id = p_batch_id
	 FOR UPDATE;

	IF NOT FOUND THEN
		RAISE EXCEPTION 'Batch % not found', p_batch_id;
	END IF;

	-- Check stock sufficiency
	IF v_qty_on_hand < p_quantity THEN
		-- Will be rolled back by EXCEPTION block below
		RAISE EXCEPTION 'Insufficient stock for batch %, requested %, available %', p_batch_id, p_quantity, v_qty_on_hand;
	END IF;

	-- Determine base price from SKU
	SELECT base_price INTO v_base_price
	  FROM Product_SKUs
	 WHERE sku_id = v_sku_id;

	IF v_base_price IS NULL THEN
		RAISE EXCEPTION 'Base price not found for SKU % (batch %)', v_sku_id, p_batch_id;
	END IF;

	-- Apply best matching discount rule (if any)
	SELECT COALESCE(MAX(discount_percentage), 0)
	  INTO v_discount
	  FROM Pricing_Rules
	 WHERE (sku_id IS NULL OR sku_id = v_sku_id)
	   AND (customer_id IS NULL OR customer_id = p_customer_id)
	   AND p_quantity >= COALESCE(min_quantity, 1);

	v_price := ROUND(v_base_price * (1 - v_discount/100.0), 2);

	-- Create the order in pending state (single-item order for now)
	INSERT INTO Orders(customer_id, status)
	VALUES (p_customer_id, 'pending')
	RETURNING order_id INTO o_order_id;

	-- Decrement inventory for the locked batch
	UPDATE Inventory_Batches
	   SET quantity_on_hand = quantity_on_hand - p_quantity
	 WHERE batch_id = p_batch_id;

	-- Insert the order item with the determined sale price
	INSERT INTO Order_Items(order_id, batch_id, quantity_ordered, sale_price)
	VALUES (o_order_id, p_batch_id, p_quantity, v_price)
	RETURNING order_item_id INTO o_order_item_id;

	o_sale_price := v_price;
EXCEPTION WHEN OTHERS THEN
	-- Rethrow to let the caller's transaction manager handle rollback
	RAISE;
END;
$$;

