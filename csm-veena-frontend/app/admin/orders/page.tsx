'use client';

import { ProtectedRoute } from '@/components/auth/protected-route';
import { AllOrders } from '@/components/admin/all-orders';
import { AdminLayout } from '@/components/layouts/admin-layout';

export default function AdminOrdersPage() {
  return (
    <ProtectedRoute requireAdmin>
      <AdminLayout>
        <AllOrders />
      </AdminLayout>
    </ProtectedRoute>
  );
}
