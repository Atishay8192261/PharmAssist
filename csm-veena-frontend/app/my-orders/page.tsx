'use client';

import { ProtectedRoute } from '@/components/auth/protected-route';
import { MyOrders } from '@/components/customer/my-orders';
import { CustomerLayout } from '@/components/layouts/customer-layout';

export default function MyOrdersPage() {
  return (
    <ProtectedRoute>
      <CustomerLayout>
        <MyOrders />
      </CustomerLayout>
    </ProtectedRoute>
  );
}
