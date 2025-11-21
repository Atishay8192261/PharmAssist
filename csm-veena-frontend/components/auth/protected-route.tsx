"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
  const router = useRouter();
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    if (requireAdmin && !isAdmin) {
      router.push("/catalog");
    }
  }, [isAuthenticated, isAdmin, isLoading, requireAdmin, router]);

  if (isLoading) return null;
  if (!isAuthenticated) return null;
  if (requireAdmin && !isAdmin) return null;
  return <>{children}</>;
}
