'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated, isAdmin } from '@/lib/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Defer auth checks to client after mount to avoid SSR localStorage access
    const authed = isAuthenticated();
    if (!authed) {
      router.replace('/login');
      setChecked(true);
      return;
    }
    if (requireAdmin && !isAdmin()) {
      router.replace('/catalog');
      setChecked(true);
      return;
    }
    setAllowed(true);
    setChecked(true);
  }, [router, requireAdmin]);

  if (!checked) {
    return null; // Optionally render a spinner
  }

  if (!allowed) {
    return null;
  }

  return <>{children}</>;
}
