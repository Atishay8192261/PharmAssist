"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { api } from "@/lib/api"
import type { Product, ProductsResponse } from "@/lib/types"
import { useCart } from "@/context/cart-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { PriceTag } from "@/components/shared/price-tag"
import { QuantityInput } from "@/components/shared/quantity-input"
import { CatalogSkeleton } from "@/components/shared/skeletons"
import { getExpirySeverity, formatDate, formatPrice } from "@/lib/utils"
import { useDebounce } from "@/hooks/use-debounce"
import { AlertCircle } from "lucide-react"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"

export default function CatalogPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { refreshCart } = useCart()

  const [data, setData] = useState<ProductsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [quantities, setQuantities] = useState<Record<number, number>>({})
  const [addingToCart, setAddingToCart] = useState<Record<number, boolean>>({})

  const page = Number(searchParams.get("page")) || 1
  const quantityPreview = Number(searchParams.get("quantity")) || 1
  const searchQuery = searchParams.get("search") || ""
  const [pendingSearch, setPendingSearch] = useState(searchQuery)
  const debouncedSearch = useDebounce(pendingSearch, 350)

  const fetchProducts = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      try {
        const res = await api.getProducts(
          {
            page,
            limit: 20,
            quantity: quantityPreview,
            search: searchQuery || undefined,
          },
          signal,
        )
        setData(res)
      } catch (error: any) {
        if (error.name !== "AbortError") {
          toast.error("Error", {
            description: "Failed to load products",
          })
        }
      } finally {
        setLoading(false)
      }
    },
    [page, quantityPreview, searchQuery],
  )

  useEffect(() => {
    const controller = new AbortController()
    fetchProducts(controller.signal)
    return () => controller.abort()
  }, [fetchProducts])

  const handleQuantityPreviewChange = (val: number) => {
    const params = new URLSearchParams(searchParams)
    params.set("quantity", val.toString())
    router.replace(`/customer/catalog?${params.toString()}`)
  }

  // Progressive search: update URL when debounced input changes
  useEffect(() => {
    const params = new URLSearchParams(searchParams)
    if (debouncedSearch.trim()) {
      params.set("search", debouncedSearch.trim())
    } else {
      params.delete("search")
    }
    params.set("page", "1")
    // Only push if value actually changed relative to current search param
    if ((searchQuery || "") !== debouncedSearch.trim()) {
      router.replace(`/customer/catalog?${params.toString()}`)
    }
  }, [debouncedSearch])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Already handled by debounce effect; noop to prevent full page reload
  }

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams)
    params.set("page", newPage.toString())
    router.push(`/customer/catalog?${params.toString()}`)
  }

  const handleAddToCart = async (product: Product) => {
    const qty = quantities[product.sku_id] || 1
    setAddingToCart((prev) => ({ ...prev, [product.sku_id]: true }))

    try {
      await api.updateCartItem(product.sku_id, qty)
      await refreshCart()
      toast.success("Added to cart", {
        description: `${qty} x ${product.product_name} added to your cart.`,
      })
    } catch (error: any) {
      toast.error("Error", {
        description: error.message || "Failed to add to cart",
      })
    } finally {
      setAddingToCart((prev) => ({ ...prev, [product.sku_id]: false }))
    }
  }

  if (loading && !data) {
    return <CatalogSkeleton />
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Product Catalog</h1>
          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3 w-full xl:w-auto">
            <div className="flex flex-1 items-center gap-2 bg-muted p-2 rounded-lg">
              <span className="text-sm font-medium whitespace-nowrap">Pricing Preview Qty:</span>
              <div className="w-24">
              <QuantityInput
                value={quantityPreview}
                onChange={handleQuantityPreviewChange}
                min={1}
                max={1000}
              />
            </div>
            </div>
            <div className="flex flex-1 items-center gap-2 bg-muted p-2 rounded-lg">
              <span className="text-sm font-medium whitespace-nowrap">Search:</span>
              <input
                type="text"
                value={pendingSearch}
                onChange={(e) => setPendingSearch(e.target.value)}
                placeholder="e.g. Paracetamol"
                className="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <Button type="submit" variant="secondary" className="shrink-0">Go</Button>
            </div>
          </form>
        </div>
        {searchQuery && (
          <p className="text-sm text-muted-foreground">
            Showing results for <span className="font-medium">"{searchQuery}"</span>
            {data && data.total_items === 0 && ", no matches found."}
          </p>
        )}
      </div>

      {data && data.total_items === 0 && !loading && (
        <div className="text-sm text-muted-foreground">No products match your search.</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 md:gap-6">
        {data?.items.map((product) => {
          const severity = getExpirySeverity(product.earliest_expiry)

          return (
            <Card key={product.sku_id} className="flex flex-col h-full transition-shadow hover:shadow-md">
              <CardHeader className="pb-2 space-y-1">
                <div className="flex justify-between items-start">
                  <CardTitle className="text-base md:text-lg font-semibold line-clamp-1" title={product.product_name}>
                    {product.product_name}
                  </CardTitle>
                  {severity !== "normal" && (
                    <Badge variant={severity === "danger" ? "destructive" : "secondary"} className="ml-2 shrink-0">
                      {severity === "danger" ? "< 7 days" : "< 30 days"}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{product.manufacturer}</p>
              </CardHeader>

              <CardContent className="grow space-y-4 text-sm">
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Package:</span>
                    <span className="font-medium">{product.package_size}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Stock:</span>
                    <span className="font-medium">{product.total_on_hand}</span>
                  </div>
                  {product.earliest_expiry && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Expiry:</span>
                      <span className={severity === "danger" ? "text-red-600 font-medium" : ""}>
                        {formatDate(product.earliest_expiry)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Base Price:</span>
                    <span className="font-medium">${formatPrice(product.base_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Your Price:</span>
                    <span className="font-medium">${formatPrice(product.effective_price)}</span>
                  </div>
                </div>
                <div className="pt-2 border-t">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-muted-foreground">Price per unit:</span>
                    <PriceTag basePrice={product.base_price} effectivePrice={product.effective_price} />
                  </div>
                </div>
              </CardContent>

              <CardFooter className="pt-2 flex flex-col gap-3">
                <div className="flex w-full items-center gap-2">
                  <div className="flex-1">
                    <QuantityInput
                      value={quantities[product.sku_id] || 1}
                      onChange={(val) => setQuantities((prev) => ({ ...prev, [product.sku_id]: val }))}
                      min={1}
                      max={product.total_on_hand}
                    />
                  </div>
                  <Button
                    onClick={() => handleAddToCart(product)}
                    disabled={addingToCart[product.sku_id] || product.total_on_hand < 1}
                    className="flex-1"
                  >
                    {addingToCart[product.sku_id] ? "Adding..." : "Add to Cart"}
                  </Button>
                </div>
                {product.total_on_hand < 1 && (
                  <p className="text-xs text-red-500 font-medium flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" /> Out of Stock
                  </p>
                )}
              </CardFooter>
            </Card>
          )
        })}
      </div>

      {data && data.total_pages > 1 && (
        <div className="pt-4 flex flex-col gap-3">
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => page > 1 && handlePageChange(page - 1)}
                  className={page <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                />
              </PaginationItem>
              {(() => {
                const total = data.total_pages
                const windowSize = 10
                let start = Math.max(1, page - Math.floor(windowSize / 2))
                let end = start + windowSize - 1
                if (end > total) {
                  end = total
                  start = Math.max(1, end - windowSize + 1)
                }
                const pages: number[] = []
                for (let p = start; p <= end; p++) pages.push(p)
                return pages.map((p) => (
                  <PaginationItem key={p}>
                    <PaginationLink isActive={page === p} onClick={() => handlePageChange(p)} className="cursor-pointer">
                      {p}
                    </PaginationLink>
                  </PaginationItem>
                ))
              })()}
              <PaginationItem>
                <PaginationNext
                  onClick={() => page < data.total_pages && handlePageChange(page + 1)}
                  className={page >= data.total_pages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
          <div className="flex items-center gap-2 text-sm">
            <span>Page</span>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const form = e.currentTarget as HTMLFormElement
                const input = form.querySelector<HTMLInputElement>('input[name="pageJump"]')
                if (!input) return
                const val = parseInt(input.value, 10)
                if (!isNaN(val) && val >= 1 && val <= data.total_pages && val !== page) {
                  handlePageChange(val)
                }
              }}
              className="flex items-center gap-2"
            >
              <input
                type="number"
                name="pageJump"
                min={1}
                max={data.total_pages}
                defaultValue={page}
                className="w-16 rounded-md border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="submit"
                className="text-sm px-3 py-1 rounded-md border bg-background hover:bg-muted transition-colors"
              >
                Go
              </button>
              <span className="text-muted-foreground">of {data.total_pages}</span>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
