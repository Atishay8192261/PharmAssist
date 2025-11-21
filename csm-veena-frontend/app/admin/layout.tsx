import type React from "react"
import { AdminLayout } from "@/components/layouts/admin-layout"
import { ProtectedRoute } from "@/components/auth/protected-route"

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute requireAdmin>
      <AdminLayout>{children}</AdminLayout>
    </ProtectedRoute>
  )
}
