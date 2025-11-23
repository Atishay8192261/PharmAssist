import type {
  LoginResponse,
  ProductsResponse,
  CartResponse,
  CartItemUpsertResponse,
  CartItemRemoveResponse,
  CheckoutResponse,
  MyOrdersResponse,
  AdminOrdersResponse,
  AdminInventoryResponse,
  OrderStatus,
  ErrorResponse,
  AdminOrderDetailsResponse,
} from "./types"
import { toNumber } from "./utils"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"

class ApiClient {
  private getAuthHeaders(): HeadersInit {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    }
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }
    return headers
  }

  private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    const headers = { ...this.getAuthHeaders(), ...options.headers }
    let response: Response
    try {
      response = await fetch(url, { ...options, headers })
    } catch (networkErr: any) {
      // Preserve AbortError so UI logic can suppress toast for canceled requests
      if (networkErr?.name === 'AbortError') {
        throw networkErr
      }
      throw {
        status: 0,
        message: networkErr?.message || 'Network request failed',
        code: 'NETWORK_ERROR',
        name: 'NetworkError'
      }
    }

    if (!response.ok) {
      // Handle 401 Unauthorized globally
      if (response.status === 401) {
        // Only force logout redirect if we actually had a token; avoid redirect loops on anonymous pages
        const hadToken = typeof window !== 'undefined' && !!localStorage.getItem('access_token')
        if (hadToken && typeof window !== "undefined") {
          localStorage.removeItem("access_token")
          window.location.href = "/login"
        }
      }

      let errorMessage = "An unexpected error occurred"
      let errorBody: ErrorResponse | null = null

      try {
        errorBody = await response.json()
        errorMessage = errorBody?.error || response.statusText
      } catch (e) {
        errorMessage = response.statusText
      }

      // Throw an object that matches our ApiError interface structure
      throw {
        status: response.status,
        message: errorMessage,
        code: errorBody?.code,
        name: 'HttpError'
      }
    }

    // For 204 No Content
    if (response.status === 204) {
      return {} as T
    }

    const data = await response.json()
    return this.normalizeNumbers(data) as T
  }

  // Recursively convert string numbers to actual numbers
  private normalizeNumbers(data: any): any {
    if (Array.isArray(data)) {
      return data.map((item) => this.normalizeNumbers(item))
    } else if (typeof data === "object" && data !== null) {
      const newData: any = {}
      for (const key in data) {
        if (
          [
            "base_price",
            "effective_price",
            "total_price",
            "cost_price",
            "estimated_total_price",
            "total_on_hand",
            "quantity_on_hand",
          ].includes(key)
        ) {
          newData[key] = toNumber(data[key])
        } else {
          newData[key] = this.normalizeNumbers(data[key])
        }
      }
      return newData
    }
    return data
  }

  // Auth
  async login(credentials: { username: string; password: string }): Promise<LoginResponse> {
    return this.fetch<LoginResponse>("/api/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    })
  }

  // Products
  async getProducts(
    params: {
      page?: number
      limit?: number
      quantity?: number
      customer_id?: number
      search?: string
    } = {},
    signal?: AbortSignal,
  ): Promise<ProductsResponse> {
    const query = new URLSearchParams()
    if (params.page) query.set("page", params.page.toString())
    if (params.limit) query.set("limit", params.limit.toString())
    if (params.quantity) query.set("quantity", params.quantity.toString())
    if (params.customer_id) query.set("customer_id", params.customer_id.toString())
    if (params.search) query.set("search", params.search)

    return this.fetch<ProductsResponse>(`/api/products?${query.toString()}`, { signal })
  }

  // Cart
  async getCart(): Promise<CartResponse> {
    return this.fetch<CartResponse>("/api/cart")
  }

  async updateCartItem(sku_id: number, quantity: number): Promise<CartItemUpsertResponse | CartItemRemoveResponse> {
    return this.fetch<CartItemUpsertResponse | CartItemRemoveResponse>("/api/cart", {
      method: "POST",
      body: JSON.stringify({ sku_id, quantity }),
    })
  }

  async checkout(): Promise<CheckoutResponse> {
    return this.fetch<CheckoutResponse>("/api/checkout", {
      method: "POST",
    })
  }

  // Orders
  async getMyOrders(): Promise<MyOrdersResponse> {
    return this.fetch<MyOrdersResponse>("/api/my-orders")
  }

  async getAllOrders(): Promise<AdminOrdersResponse> {
    return this.fetch<AdminOrdersResponse>("/api/admin/all-orders")
  }

  async updateOrderStatus(order_id: number, status: OrderStatus): Promise<{ order_id: number; status: OrderStatus }> {
    return this.fetch<{ order_id: number; status: OrderStatus }>(`/api/admin/orders/${order_id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    })
  }

  async getAdminOrderDetails(order_id: number): Promise<AdminOrderDetailsResponse> {
    return this.fetch<AdminOrderDetailsResponse>(`/api/admin/orders/${order_id}/items`)
  }

  // Inventory
  async getAdminInventory(params: { page?: number; limit?: number; search?: string; filter?: string } = {}): Promise<AdminInventoryResponse> {
    const query = new URLSearchParams()
    if (params.page) query.set("page", String(params.page))
    if (params.limit) query.set("limit", String(params.limit))
    if (params.search) query.set("search", params.search)
    if (params.filter) query.set("filter", params.filter)
    const qs = query.toString()
    return this.fetch<AdminInventoryResponse>(`/api/admin/inventory${qs ? "?" + qs : ""}`)
  }

  async getAdminDashboardStats(): Promise<import("./types").AdminDashboardStats> {
    return this.fetch<import("./types").AdminDashboardStats>("/api/admin/dashboard-stats")
  }

  // Legacy / NLP
  async addInventoryNLP(text: string): Promise<any> {
    return this.fetch("/api/admin/add-inventory-nlp", {
      method: "POST",
      body: JSON.stringify({ text }),
    })
  }

  // Inventory CRUD
  async createInventoryBatch(payload: { sku_id?: number; sku_name?: string; batch_no: string; quantity: number; expiry_date: string }): Promise<any> {
    return this.fetch("/api/admin/inventory/batches", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async updateInventoryBatch(batch_id: number, payload: { quantity_on_hand?: number; expiry_date?: string; cost_price?: number }): Promise<any> {
    return this.fetch(`/api/admin/inventory/batches/${batch_id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    })
  }

  async deleteInventoryBatch(batch_id: number): Promise<{ deleted: boolean; batch_id: number }> {
    return this.fetch<{ deleted: boolean; batch_id: number }>(`/api/admin/inventory/batches/${batch_id}`, {
      method: "DELETE",
    })
  }

  // Product & SKU creation
  async createProduct(payload: { name: string; manufacturer?: string; description?: string }): Promise<any> {
    return this.fetch("/api/admin/products", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async createSku(payload: { product_id: number; package_size: string; unit_type: string; base_price: number }): Promise<any> {
    return this.fetch("/api/admin/skus", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }
}

export const api = new ApiClient()
