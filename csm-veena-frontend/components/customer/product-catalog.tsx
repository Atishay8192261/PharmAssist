'use client';

import { useState } from 'react';
import { Product } from '@/lib/types';
import { useProducts } from '@/hooks/useProducts';
import { getCurrentUser } from '@/lib/auth';
import { ProductCard } from './product-card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';

export function ProductCatalog() {
  const [error, setError] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [orderSuccess, setOrderSuccess] = useState('');

  const user = getCurrentUser();
  const customerId = user?.customer_id;

  const { products, loading, error: swrError, refresh } = useProducts({
    quantity,
    customer_id: customerId,
  });
  // Merge SWR error into local error display
  if (!error && swrError) setError(swrError.message || 'Failed to load products');

  const handleOrderSuccess = (message: string) => {
    setOrderSuccess(message);
    refresh(); // Refresh products to update stock
    setTimeout(() => setOrderSuccess(''), 5000);
  };

  return (
    <div className="space-y-6">
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
            onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
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
    </div>
  );
}
