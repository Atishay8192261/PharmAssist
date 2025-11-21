import { ProtectedRoute } from '@/components/auth/protected-route';
import { CustomerLayout } from '@/components/layouts/customer-layout';

export default function CustomerGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <CustomerLayout>{children}</CustomerLayout>
    </ProtectedRoute>
  );
}
