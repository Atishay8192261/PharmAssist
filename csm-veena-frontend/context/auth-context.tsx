"use client"

import type React from "react"
import { createContext, useContext, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Role, type User, type JWTPayload } from "@/lib/types"

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string) => void
  logout: () => void
  isAdmin: boolean
  isCustomer: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem("access_token")
    if (token) {
      try {
        // Basic JWT decoding (in a real app, use a library like jwt-decode)
        const base64Url = token.split(".")[1]
        const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
        const jsonPayload = decodeURIComponent(
          window
            .atob(base64)
            .split("")
            .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
            .join(""),
        )

        const payload: JWTPayload = JSON.parse(jsonPayload)

        // Check expiry
        if (payload.exp * 1000 < Date.now()) {
          logout()
        } else {
          setUser({
            user_id: payload.sub,
            username: payload.username,
            role: payload.role,
            customer_id: payload.customer_id,
          })
        }
      } catch (e) {
        console.error("Failed to decode token", e)
        logout()
      }
    }
    setIsLoading(false)
  }, [])

  const login = (token: string) => {
    localStorage.setItem("access_token", token)
    try {
      const base64Url = token.split(".")[1]
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
      const jsonPayload = decodeURIComponent(
        window
          .atob(base64)
          .split("")
          .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
          .join("")
      )
      const payload: JWTPayload = JSON.parse(jsonPayload)
      if (payload.exp * 1000 < Date.now()) {
        logout()
        return
      }
      const builtUser: User = {
        user_id: typeof payload.sub === "string" ? Number(payload.sub) : payload.sub,
        username: payload.username,
        role: payload.role,
        customer_id: payload.customer_id,
      }
      setUser(builtUser)
      if (builtUser.role === Role.ADMIN) {
        router.push("/admin")
      } else {
        router.push("/catalog")
      }
    } catch (e) {
      console.error("Failed to decode token during login", e)
      logout()
    }
  }

  const logout = () => {
    localStorage.removeItem("access_token")
    setUser(null)
    router.push("/login")
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        isAdmin: user?.role === Role.ADMIN,
        isCustomer: user?.role === Role.CUSTOMER,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
