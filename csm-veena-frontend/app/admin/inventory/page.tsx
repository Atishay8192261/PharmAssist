'use client';

import { ProtectedRoute } from '@/components/auth/protected-route';
import { AIInventory } from '@/components/admin/ai-inventory';
import { AdminLayout } from '@/components/layouts/admin-layout';

export default function AdminInventoryPage() {
  return (
    <ProtectedRoute requireAdmin>
      <AdminLayout>
        <AIInventory />
      </AdminLayout>
    </ProtectedRoute>
  );
}
