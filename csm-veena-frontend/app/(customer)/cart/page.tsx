"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import type { CartResponse, CartItem } from "@/lib/types"
import { useCart } from "@/context/cart-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "sonner"
import { PriceTag } from "@/components/shared/price-tag"
import { QuantityInput } from "@/components/shared/quantity-input"
import { TableRowsSkeleton } from "@/components/shared/skeletons"
import { formatPrice } from "@/lib/utils"
import { Trash2, ArrowRight, ShoppingBag, Home, List } from "lucide-react"
import Link from "next/link"

export default function CartPage() {
  const router = useRouter()
  const { refreshCart } = useCart()

  const [cart, setCart] = useState<CartResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<Record<number, boolean>>({})
  const [checkingOut, setCheckingOut] = useState(false)

  const fetchCart = async () => {
    try {
      const res = await api.getCart()
      setCart(res)
    } catch (error) {
      toast.error("Error", {
        description: "Failed to load cart",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCart()
  }, [])

  const handleUpdateQuantity = async (item: CartItem, newQuantity: number) => {
    // Guard: ignore no-op updates or invalid quantities
    if (newQuantity === item.quantity) return
    if (newQuantity < 0) return
    // Prevent overlapping updates for same sku
    if (updating[item.sku_id]) return
    setUpdating((prev) => ({ ...prev, [item.sku_id]: true }))
    try {
      // Optional upper bound safeguard if backend enforces max per item (assume >0)
      // const safeQty = Math.max(0, newQuantity)
      await api.updateCartItem(item.sku_id, newQuantity)
      await fetchCart()
      await refreshCart()
    } catch (error: any) {
      toast.error("Error", {
        description: error.message || "Failed to update cart",
      })
    } finally {
      setUpdating((prev) => ({ ...prev, [item.sku_id]: false }))
    }
  }

  const handleRemoveItem = async (item: CartItem) => {
    if (!confirm("Are you sure you want to remove this item?")) return
    await handleUpdateQuantity(item, 0)
  }

  const handleCheckout = async () => {
    setCheckingOut(true)
    try {
      const res = await api.checkout()
      await refreshCart()
      toast.success("Order Placed!", {
        description: `Order #${res.order_id} has been successfully placed.`,
      })
      router.push("/my-orders")
    } catch (error: any) {
      if (error.status === 409) {
        toast.error("Insufficient Stock", {
          description: "Some items in your cart are no longer available. Please review your cart.",
        })
        fetchCart()
      } else {
        toast.error("Checkout Failed", {
          description: error.message || "An error occurred during checkout.",
        })
      }
    } finally {
      setCheckingOut(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto px-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Shopping Cart</h1>
          <div className="flex items-center gap-2">
            <Link href="/customer/catalog" className="inline-flex items-center gap-1 text-sm font-medium hover:text-primary">
              <Home className="h-4 w-4" /> Home
            </Link>
            <Link href="/customer/my-orders" className="inline-flex items-center gap-1 text-sm font-medium hover:text-primary">
              <List className="h-4 w-4" /> My Orders
            </Link>
          </div>
        </div>
        <Card>
          <CardContent className="p-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRowsSkeleton rows={3} cells={5} />
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="bg-muted p-6 rounded-full">
          <ShoppingBag className="h-12 w-12 text-muted-foreground" />
        </div>
        <h2 className="text-2xl font-semibold">Your cart is empty</h2>
        <p className="text-muted-foreground">Looks like you haven't added anything yet.</p>
        <Link href="/catalog">
          <Button size="lg" className="mt-4">
            Browse Catalog
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto px-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Shopping Cart</h1>
        <div className="flex items-center gap-2">
          <Link href="/customer/catalog" className="inline-flex items-center gap-1 text-sm font-medium hover:text-primary">
            <Home className="h-4 w-4" /> Home
          </Link>
          <Link href="/customer/my-orders" className="inline-flex items-center gap-1 text-sm font-medium hover:text-primary">
            <List className="h-4 w-4" /> My Orders
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40%]">Product</TableHead>
                    <TableHead>Quantity</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cart.items.map((item) => (
                    <TableRow key={item.cart_item_id}>
                      <TableCell>
                        <div className="font-medium">{item.product_name}</div>
                        <div className="text-sm text-muted-foreground">{item.package_size}</div>
                        <div className="text-xs text-muted-foreground">{item.manufacturer}</div>
                      </TableCell>
                      <TableCell>
                        <QuantityInput
                          value={item.quantity}
                          onChange={(val) => handleUpdateQuantity(item, val)}
                          disabled={updating[item.sku_id]}
                          max={item.available_stock ?? 9999}
                          min={1}
                        />
                        {typeof item.available_stock === "number" && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Available: {item.available_stock}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <PriceTag basePrice={item.base_price} effectivePrice={item.effective_price} size="sm" />
                      </TableCell>
                      <TableCell className="font-medium">
                        ${formatPrice(item.quantity * item.effective_price)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveItem(item)}
                          disabled={updating[item.sku_id]}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>Order Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total Items</span>
                <span>{cart.total_items}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total Quantity</span>
                <span>{cart.total_quantity}</span>
              </div>
              <div className="border-t pt-4 flex justify-between items-center font-bold text-lg">
                <span>Total</span>
                <span>${formatPrice(cart.estimated_total_price)}</span>
              </div>
            </CardContent>
            <CardFooter>
              <Button className="w-full" size="lg" onClick={handleCheckout} disabled={checkingOut}>
                {checkingOut ? "Processing..." : "Checkout"}
                {!checkingOut && <ArrowRight className="ml-2 h-4 w-4" />}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  )
}
