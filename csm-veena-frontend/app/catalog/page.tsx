'use client';

import { ProtectedRoute } from '@/components/auth/protected-route';
import { ProductCatalog } from '@/components/customer/product-catalog';
import { CustomerLayout } from '@/components/layouts/customer-layout';

export default function CatalogPage() {
  return (
    <ProtectedRoute>
      <CustomerLayout>
        <ProductCatalog />
      </CustomerLayout>
    </ProtectedRoute>
  );
}
