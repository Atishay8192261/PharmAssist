"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/context/auth-context"

export default function HomePage() {
  const router = useRouter()
  const { isAuthenticated, isAdmin, isLoading } = useAuth()

  useEffect(() => {
    if (isLoading) return

    if (!isAuthenticated) {
      router.push("/login")
    } else if (isAdmin) {
      router.push("/admin/orders")
    } else {
      router.push("/catalog")
    }
  }, [isAuthenticated, isAdmin, isLoading, router])

  return null
}
