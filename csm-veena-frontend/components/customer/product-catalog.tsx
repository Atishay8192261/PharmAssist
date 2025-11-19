'use client';

import { useState, useEffect } from 'react';
import { apiClient, Product } from '@/lib/api';
import { getCurrentUser } from '@/lib/auth';
import { ProductCard } from './product-card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function ProductCatalog() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [orderSuccess, setOrderSuccess] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const user = getCurrentUser();
  const customerId = user?.customer_id;

  useEffect(() => {
    loadProducts();
  }, [quantity, customerId, currentPage]);

  const loadProducts = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await apiClient.getProducts({
        customerId: customerId || undefined,
        quantity,
        page: currentPage,
        limit: 20,
      });
      setProducts(response.items);
      if (typeof response.total_pages === 'number') setTotalPages(response.total_pages);
      if (typeof response.current_page === 'number') setCurrentPage(response.current_page);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const handleOrderSuccess = (message: string) => {
    setOrderSuccess(message);
    loadProducts(); // Refresh products to update stock
    setTimeout(() => setOrderSuccess(''), 5000);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Product Catalog</h1>
        <p className="text-muted-foreground mt-2">
          Browse available pharmaceutical products and place orders
        </p>
      </div>

      {orderSuccess && (
        <Alert className="bg-green-50 border-green-200">
          <AlertDescription className="text-green-800">{orderSuccess}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-end gap-4 bg-card p-4 rounded-lg border">
        <div className="flex-1 max-w-xs">
          <Label htmlFor="quantity">Assumed Quantity for Pricing</Label>
          <Input
            id="quantity"
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => {
              const q = Math.max(1, parseInt(e.target.value) || 1);
              setQuantity(q);
              setCurrentPage(1); // reset to first page when pricing quantity changes
            }}
            className="mt-2"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No products available</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <ProductCard
              key={product.sku_id}
              product={product}
              onOrderSuccess={handleOrderSuccess}
            />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      <div className="flex items-center justify-between py-4">
        <Button
          variant="outline"
          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          disabled={currentPage <= 1 || loading}
        >
          Previous Page
        </Button>
        <div className="text-sm text-muted-foreground">
          Page {currentPage} of {totalPages}
        </div>
        <Button
          variant="outline"
          onClick={() => setCurrentPage((p) => (p < totalPages ? p + 1 : p))}
          disabled={currentPage >= totalPages || loading}
        >
          Next Page
        </Button>
      </div>
    </div>
  );
}
