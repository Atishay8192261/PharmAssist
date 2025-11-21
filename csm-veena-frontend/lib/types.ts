export enum Role {
  CUSTOMER = "customer",
  ADMIN = "admin",
}

export enum OrderStatus {
  PENDING = "pending",
  PROCESSED = "processed",
  SHIPPED = "shipped",
  CANCELLED = "cancelled",
}

export interface User {
  user_id: number
  username: string
  role: Role
  customer_id?: number | null
}

export interface JWTPayload {
  // Backend currently encodes sub as a string; accept both to be resilient
  sub: string | number
  username: string
  role: Role
  customer_id?: number | null
  exp: number
}

export interface LoginResponse {
  access_token: string
  token_type: string
  // Some environments may not return a user object; optional here
  user?: User
}

export interface Product {
  product_id: number
  product_name: string
  manufacturer: string
  description?: string | null
  sku_id: number
  package_size: string
  unit_type: string
  base_price: number
  effective_price: number
  total_on_hand: number
  earliest_expiry?: string | null
}

export interface ProductsResponse {
  customer_id?: number | null
  assumed_quantity_for_pricing: number
  items: Product[]
  total_items: number
  total_pages: number
  current_page: number
  page_size: number
}

export interface CartItem {
  cart_item_id: number
  sku_id: number
  quantity: number
  product_name: string
  manufacturer: string
  unit_type: string
  package_size: string
  base_price: number
  effective_price: number
  available_stock?: number
  description?: string | null
  // Frontend derived property
  subtotal?: number
}

export interface CartResponse {
  cart_id: number
  items: CartItem[]
  total_items: number
  total_quantity: number
  estimated_total_price: number
}

export interface CartItemUpsertResponse {
  cart_id: number
  item: CartItem
  removed: boolean
}

export interface CartItemRemoveResponse {
  cart_id: number
  removed: boolean
  sku_id: number
  quantity: 0
}

export interface CheckoutResponse {
  order_id: number
  status: OrderStatus
  total_price: number
  order_item_rows: number
}

export interface OrderSummary {
  order_id: number
  order_date: string
  status: OrderStatus
  total_price: number
  total_quantity: number
}

export interface MyOrdersResponse {
  customer_id: number
  orders: OrderSummary[]
}

export interface AdminOrder extends OrderSummary {
  customer_id: number
}

export interface AdminOrdersResponse {
  orders: AdminOrder[]
}

export interface AdminInventoryBatch {
  batch_id: number
  sku_name: string
  batch_no: string
  expiry_date: string
  quantity_on_hand: number
  cost_price: number
}

export interface AdminInventoryResponse {
  batches: AdminInventoryBatch[]
  total_batches: number
}

export interface DashboardDayPoint {
  day: string
  revenue: number
  profit: number
}

export interface DashboardWeekPoint {
  week_start: string
  revenue: number
  profit: number
}

export interface AdminDashboardStats {
  total_revenue: number
  total_profit: number
  total_orders: number
  total_batches: number
  expiring_soon: number
  low_stock_count: number
  daily: DashboardDayPoint[]
  weekly: DashboardWeekPoint[]
}

export interface ErrorResponse {
  error: string
  code?: string
}

// Admin Order Details
export interface AdminOrderItemDetail {
  order_item_id: number
  sku_id: number
  sku_name: string
  batch_id: number
  batch_no: string
  quantity: number
  base_price: number
  sale_price: number
  cost_price: number
  discount_pct: number
  line_total: number
  line_profit: number
}

export interface AdminOrderMeta {
  order_id: number
  customer_id: number
  order_date: string | null
  status: OrderStatus
}

export interface AdminOrderDetailsResponse {
  order: AdminOrderMeta
  items: AdminOrderItemDetail[]
  totals: {
    total_quantity: number
    total_price: number
    total_profit: number
  }
}
