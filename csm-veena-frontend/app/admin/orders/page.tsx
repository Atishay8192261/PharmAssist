"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { type AdminOrdersResponse, OrderStatus, type AdminOrderDetailsResponse } from "@/lib/types"
import { Card, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { TableSkeleton } from "@/components/shared/skeletons"
import { formatPrice, formatDateTime } from "@/lib/utils"
import { toast } from "sonner"
import { StatusBadge } from "@/components/shared/status-badge"
import * as Dialog from "@radix-ui/react-dialog"
import { Button } from "@/components/ui/button"

export default function AdminOrdersPage() {
  const [data, setData] = useState<AdminOrdersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<Record<number, boolean>>({})
  const [viewOrderId, setViewOrderId] = useState<number | null>(null)
  const [details, setDetails] = useState<AdminOrderDetailsResponse | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const res = await api.getAllOrders()
        setData(res)
      } catch (error) {
        toast.error("Error", {
          description: "Failed to load orders",
        })
      } finally {
        setLoading(false)
      }
    }

    fetchOrders()
  }, []) // Removed toast from dependency array

  const handleStatusChange = async (orderId: number, newStatus: OrderStatus) => {
    // Optimistic update
    const previousData = data ? { ...data } : null

    setData((prev) => {
      if (!prev) return null
      return {
        ...prev,
        orders: prev.orders.map((order) => (order.order_id === orderId ? { ...order, status: newStatus } : order)),
      }
    })

    setUpdating((prev) => ({ ...prev, [orderId]: true }))

    try {
      await api.updateOrderStatus(orderId, newStatus)
      toast.success("Status Updated", {
        description: `Order #${orderId} marked as ${newStatus}.`,
      })
    } catch (error: any) {
      // Revert on failure
      setData(previousData)
      toast.error("Update Failed", {
        description: error.message || "Failed to update order status",
      })
    } finally {
      setUpdating((prev) => ({ ...prev, [orderId]: false }))
    }
  }

  const openDetails = async (orderId: number) => {
    setViewOrderId(orderId)
    setDetails(null)
    setDetailsLoading(true)
    try {
      const res = await api.getAdminOrderDetails(orderId)
      setDetails(res)
    } catch (error: any) {
      toast.error("Failed to load order details", { description: error?.message || "Unknown error" })
    } finally {
      setDetailsLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">Order Management</h1>
        <Card>
          <CardContent className="p-6">
            <TableSkeleton rows={10} cells={6} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Order Management</h1>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order ID</TableHead>
                <TableHead>Customer ID</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Current Status</TableHead>
                <TableHead>Update Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.orders.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No orders found.
                  </TableCell>
                </TableRow>
              ) : (
                data?.orders.map((order) => (
                  <TableRow key={order.order_id}>
                    <TableCell className="font-medium">#{order.order_id}</TableCell>
                    <TableCell>#{order.customer_id}</TableCell>
                    <TableCell>{formatDateTime(order.order_date)}</TableCell>
                    <TableCell>
                      <StatusBadge status={order.status} />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={order.status}
                        onValueChange={(val) => handleStatusChange(order.order_id, val as OrderStatus)}
                        disabled={updating[order.order_id]}
                      >
                        <SelectTrigger className="w-[140px] h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={OrderStatus.PENDING}>Pending</SelectItem>
                          <SelectItem value={OrderStatus.PROCESSED}>Processed</SelectItem>
                          <SelectItem value={OrderStatus.SHIPPED}>Shipped</SelectItem>
                          <SelectItem value={OrderStatus.CANCELLED}>Cancelled</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => openDetails(order.order_id)}>View</Button>
                    </TableCell>
                    <TableCell className="text-right font-medium">${formatPrice(order.total_price)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog.Root open={viewOrderId !== null} onOpenChange={(open) => !open && setViewOrderId(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 w-[95vw] max-w-4xl -translate-x-1/2 -translate-y-1/2 rounded-md bg-white p-4 shadow-lg focus:outline-none">
            <div className="flex items-center justify-between mb-3">
              <Dialog.Title className="text-lg font-semibold">Order Details {viewOrderId && `#${viewOrderId}`}</Dialog.Title>
              <Dialog.Close asChild>
                <Button variant="ghost" size="sm">Close</Button>
              </Dialog.Close>
            </div>

            {detailsLoading && (
              <div className="text-sm text-muted-foreground">Loading…</div>
            )}

            {!detailsLoading && details && (
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  Customer #{details.order.customer_id} • {details.order.order_date ? formatDateTime(details.order.order_date) : ""} • {details.order.status}
                </div>
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU</TableHead>
                        <TableHead>Batch</TableHead>
                        <TableHead className="text-right">Qty</TableHead>
                        <TableHead className="text-right">Base</TableHead>
                        <TableHead className="text-right">Sale</TableHead>
                        <TableHead className="text-right">Cost</TableHead>
                        <TableHead className="text-right">Adj %</TableHead>
                        <TableHead className="text-right">Line Total</TableHead>
                        <TableHead className="text-right">Line Profit</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {details.items.map((it) => (
                        <TableRow key={it.order_item_id}>
                          <TableCell>
                            <div className="font-medium">{it.sku_name}</div>
                            <div className="text-xs text-muted-foreground">SKU #{it.sku_id}</div>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{it.batch_no}</TableCell>
                          <TableCell className="text-right">{it.quantity}</TableCell>
                          <TableCell className="text-right">${formatPrice(it.base_price)}</TableCell>
                          <TableCell className="text-right">${formatPrice(it.sale_price)}</TableCell>
                          <TableCell className="text-right">${formatPrice(it.cost_price)}</TableCell>
                          <TableCell className="text-right">
                            {(() => {
                              const base = it.base_price
                              const sale = it.sale_price
                              const cost = it.cost_price
                              if (base > 0 && sale < base) {
                                // discount vs base
                                return `-${(((base - sale) / base) * 100).toFixed(2)}%`
                              }
                              if (cost > 0 && sale >= base && sale > cost) {
                                // margin vs cost
                                return `+${(((sale - cost) / cost) * 100).toFixed(2)}%`
                              }
                              if (sale >= base && cost > 0 && sale <= cost) {
                                // sale at or below cost after floor (edge)
                                return '0%'
                              }
                              return '0%'
                            })()}
                          </TableCell>
                          <TableCell className="text-right">${formatPrice(it.line_total)}</TableCell>
                          <TableCell className="text-right">${formatPrice(it.line_profit)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <div className="flex justify-end gap-8 text-sm">
                  <div>Qty: <span className="font-medium">{details.totals.total_quantity}</span></div>
                  <div>Total: <span className="font-medium">${formatPrice(details.totals.total_price)}</span></div>
                  <div>Profit: <span className="font-medium">${formatPrice(details.totals.total_profit)}</span></div>
                </div>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
