const API_BASE_URL = 'http://localhost:5000';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface JWTPayload {
  sub: string;
  username: string;
  role: 'admin' | 'customer';
  customer_id: number | null;
  exp: number;
}

export interface Product {
  product_id: number;
  product_name: string;
  manufacturer: string;
  description: string;
  sku_id: number;
  package_size: string;
  unit_type: string;
  base_price: number;
  total_on_hand: number;
  earliest_expiry: string;
  effective_price: number;
}

export interface ProductsResponse {
  customer_id?: number;
  assumed_quantity_for_pricing: number;
  items: Product[];
}

export interface PlaceOrderRequest {
  customer_id: number;
  batch_id: number;
  quantity: number;
}

export interface PlaceOrderResponse {
  order_id: number;
  order_item_id: number;
  sale_price: number;
  status: string;
}

export interface Order {
  order_id: number;
  order_date: string;
  status: string;
  total_quantity: number;
  total_price: number;
  customer_id?: number;
}

export interface MyOrdersResponse {
  customer_id: number;
  orders: Order[];
}

export interface AllOrdersResponse {
  orders: Order[];
}

export interface AddInventoryNLPRequest {
  text: string;
}

export interface AddInventoryNLPResponse {
  message: string;
  batch_id: number;
  sku_id: number;
  batch_no: string;
  quantity_added: number;
  new_quantity_on_hand: number;
  expiry_date: string;
  source: string;
}

export interface ErrorResponse {
  error: string;
  raw?: string;
}

class ApiClient {
  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('access_token');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const res = await fetch(`${API_BASE_URL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });
    
    if (!res.ok) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Login failed');
    }
    
    return res.json();
  }

  async getProducts(params?: { customerId?: number; quantity?: number }): Promise<ProductsResponse> {
    const url = new URL(`${API_BASE_URL}/api/products`);
    if (params?.customerId) {
      url.searchParams.set('customer_id', params.customerId.toString());
    }
    if (params?.quantity) {
      url.searchParams.set('quantity', params.quantity.toString());
    }

    const res = await fetch(url.toString());
    if (!res.ok) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Failed to load products');
    }
    
    return res.json();
  }

  async placeOrder(order: PlaceOrderRequest): Promise<PlaceOrderResponse> {
    const res = await fetch(`${API_BASE_URL}/api/orders`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(order),
    });

    if (res.status === 409) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Insufficient stock');
    }

    if (!res.ok) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Order failed');
    }

    return res.json();
  }

  async getMyOrders(): Promise<MyOrdersResponse> {
    const res = await fetch(`${API_BASE_URL}/api/my-orders`, {
      headers: this.getAuthHeaders(),
    });

    if (!res.ok) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Failed to load orders');
    }

    return res.json();
  }

  async getAllOrders(): Promise<AllOrdersResponse> {
    const res = await fetch(`${API_BASE_URL}/api/admin/all-orders`, {
      headers: this.getAuthHeaders(),
    });

    if (!res.ok) {
      const error: ErrorResponse = await res.json();
      throw new Error(error.error || 'Failed to load all orders');
    }

    return res.json();
  }

  async addInventoryNLP(request: AddInventoryNLPRequest): Promise<AddInventoryNLPResponse> {
    const res = await fetch(`${API_BASE_URL}/api/admin/add-inventory-nlp`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'AI inventory failed');
    }

    return data;
  }
}

export const apiClient = new ApiClient();
