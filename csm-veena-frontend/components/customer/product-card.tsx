'use client';

import { useState } from 'react';
import { Product, apiClient } from '@/lib/api';
import { getCurrentUser } from '@/lib/auth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Package, AlertCircle } from 'lucide-react';

interface ProductCardProps {
  product: Product;
  onOrderSuccess: (message: string) => void;
}

export function ProductCard({ product, onOrderSuccess }: ProductCardProps) {
  const [orderQuantity, setOrderQuantity] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const user = getCurrentUser();
  const customerId = user?.customer_id;

  const isOutOfStock = product.total_on_hand <= 0;
  const isLowStock = product.total_on_hand > 0 && product.total_on_hand <= 10;

  const handleOrder = async () => {
    if (!customerId) {
      setError('Customer ID not found');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Note: The API expects batch_id, but the product catalog doesn't provide individual batches
      // In a real implementation, you'd need to fetch batches or have a batch selection mechanism
      // For now, we'll use sku_id as a placeholder - this may need adjustment based on your actual backend
      await apiClient.placeOrder({
        customer_id: customerId,
        batch_id: product.sku_id, // This should be actual batch_id in production
        quantity: orderQuantity,
      });
      
      onOrderSuccess(`Successfully ordered ${orderQuantity} ${product.unit_type}(s) of ${product.product_name}`);
      setOrderQuantity(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place order');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{product.product_name}</CardTitle>
            <CardDescription>{product.manufacturer}</CardDescription>
          </div>
          <Package className="h-5 w-5 text-muted-foreground" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{product.description}</p>
        
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Package:</span>
            <span className="font-medium">{product.package_size}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Base Price:</span>
            <span className="font-medium">${product.base_price.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Your Price:</span>
            <span className="font-semibold text-primary">${product.effective_price.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Stock:</span>
            <div className="flex items-center gap-2">
              <span className={isOutOfStock ? 'text-destructive font-medium' : isLowStock ? 'text-yellow-600 font-medium' : ''}>
                {product.total_on_hand} available
              </span>
              {isLowStock && !isOutOfStock && (
                <Badge variant="outline" className="text-yellow-600 border-yellow-600">Low</Badge>
              )}
            </div>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Expiry:</span>
            <span>{new Date(product.earliest_expiry).toLocaleDateString()}</span>
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor={`quantity-${product.sku_id}`}>Order Quantity</Label>
          <Input
            id={`quantity-${product.sku_id}`}
            type="number"
            min="1"
            max={product.total_on_hand}
            value={orderQuantity}
            onChange={(e) => setOrderQuantity(Math.max(1, parseInt(e.target.value) || 1))}
            disabled={isOutOfStock || loading}
          />
        </div>

        <Button
          onClick={handleOrder}
          disabled={isOutOfStock || loading}
          className="w-full"
        >
          {loading ? 'Placing Order...' : isOutOfStock ? 'Out of Stock' : 'Place Order'}
        </Button>
      </CardContent>
    </Card>
  );
}
