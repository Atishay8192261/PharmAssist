'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated, isAdmin } from '@/lib/auth';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login');
    } else if (isAdmin()) {
      router.push('/admin/orders');
    } else {
      router.push('/catalog');
    }
  }, [router]);

  return null;
}
