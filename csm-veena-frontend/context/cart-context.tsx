"use client"

import type React from "react"
import { createContext, useContext, useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"
import { useAuth } from "./auth-context"

interface CartContextType {
  cartCount: number
  refreshCart: () => Promise<void>
}

const CartContext = createContext<CartContextType | undefined>(undefined)

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cartCount, setCartCount] = useState(0)
  const { isCustomer } = useAuth()

  const refreshCart = useCallback(async () => {
    if (!isCustomer) return
    try {
      const cart = await api.getCart()
      setCartCount(cart.total_quantity || 0)
    } catch (error) {
      console.error("Failed to fetch cart count", error)
    }
  }, [isCustomer])

  useEffect(() => {
    if (isCustomer) {
      refreshCart()
    } else {
      setCartCount(0)
    }
  }, [isCustomer, refreshCart])

  return <CartContext.Provider value={{ cartCount, refreshCart }}>{children}</CartContext.Provider>
}

export function useCart() {
  const context = useContext(CartContext)
  if (context === undefined) {
    throw new Error("useCart must be used within a CartProvider")
  }
  return context
}
