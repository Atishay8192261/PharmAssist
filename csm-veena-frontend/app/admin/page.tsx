"use client"

import { useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { useInventory } from "@/hooks/useInventory"
import type { AdminInventoryResponse, AdminOrder, AdminDashboardStats } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import Link from "next/link"

export default function AdminDashboardPage() {
  const [orders, setOrders] = useState<AdminOrder[]>([])
  const [inventory, setInventory] = useState<AdminInventoryResponse | null>(null)
  const [stats, setStats] = useState<AdminDashboardStats | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    const run = async () => {
      if (!active) return
      setLoading(true)
      try {
        const [o, inv, st] = await Promise.all([
          api.getAllOrders(),
          api.getAdminInventory({ filter: 'critical', limit: 100 }),
          api.getAdminDashboardStats(),
        ])
        if (!active) return
        setOrders(o.orders)
        setInventory(inv)
        setStats(st)
      } catch {
        if (!active) return
        // Fallback empty state if API errors (e.g., no auth or network)
        setOrders([])
        setInventory({ batches: [], total_batches: 0 })
      } finally {
        if (active) setLoading(false)
      }
    }
    run()
    return () => { active = false }
  }, [])

  const totalRevenue = stats?.total_revenue ?? 0
  const totalProfit = stats?.total_profit ?? 0
  const expiringSoon = stats?.expiring_soon ?? 0
  const lowStockCount = stats?.low_stock_count ?? 0

  const totalOrders = stats?.total_orders ?? orders.length
  const latestOrders = orders.slice(0, 5)

  const lowStockBatches = useMemo(() => {
    const batches = inventory?.batches || []
    return batches.sort((a,b)=> (a.quantity_on_hand||0)-(b.quantity_on_hand||0)).slice(0,5)
  }, [inventory])

  const dailyPoints = stats?.daily ?? []
  const revenueColor = '#0A5FFF'
  const profitColor = '#16A34A'

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
        <div className="flex gap-2">
          <Button asChild variant="outline"><Link href="/admin/orders">All Orders</Link></Button>
          <Button asChild variant="outline"><Link href="/admin/inventory">Inventory Management</Link></Button>
          <Button asChild variant="outline"><Link href="/admin/inventory/view">Inventory View</Link></Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Total Revenue</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : `$${totalRevenue.toFixed(2)}`}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Total Orders</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : totalOrders}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Total Batches</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : (stats?.total_batches ?? 0)}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Total Profit</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : `$${totalProfit.toFixed(2)}`}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Expiring ≤30d</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : expiringSoon}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Low Stock (≤5)</CardTitle></CardHeader>
          <CardContent className="text-3xl font-bold">{loading ? '…' : lowStockCount}</CardContent>
        </Card>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent Orders</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order ID</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow><TableCell colSpan={4} className="text-muted-foreground">Loading…</TableCell></TableRow>
                )}
                {!loading && latestOrders.length === 0 && (
                  <TableRow><TableCell colSpan={4} className="text-muted-foreground">No orders yet</TableCell></TableRow>
                )}
                {latestOrders.map(o => (
                  <TableRow key={o.order_id}>
                    <TableCell>#{o.order_id}</TableCell>
                    <TableCell>{new Date(o.order_date).toLocaleString()}</TableCell>
                    <TableCell><Badge variant="outline">{o.status}</Badge></TableCell>
                    <TableCell className="text-right">${(o.total_price || 0).toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Low Stock ({'<='}5)</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Batch</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow><TableCell colSpan={4} className="text-muted-foreground">Loading…</TableCell></TableRow>
                )}
                {!loading && lowStockBatches.length === 0 && (
                  <TableRow><TableCell colSpan={4} className="text-muted-foreground">All good on stock</TableCell></TableRow>
                )}
                {lowStockBatches.map(b => (
                  <TableRow key={b.batch_id}>
                    <TableCell>{b.sku_name}</TableCell>
                    <TableCell className="font-mono text-xs">{b.batch_no}</TableCell>
                    <TableCell>{b.expiry_date}</TableCell>
                    <TableCell className="text-right">{b.quantity_on_hand}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>14-Day Revenue vs Profit</CardTitle></CardHeader>
        <CardContent>
          {dailyPoints.length === 0 && !loading && (
            <p className="text-sm text-muted-foreground">No sales data yet</p>
          )}
          {dailyPoints.length === 0 && loading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {dailyPoints.length > 0 && (
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={dailyPoints} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" tickFormatter={(v) => String(v).slice(5)} />
                  <YAxis />
                  <Tooltip formatter={(val: number) => `$${val.toFixed(2)}`} labelFormatter={(l) => `Date: ${l}`} />
                  <Legend />
                  <Line type="monotone" dataKey="revenue" name="Revenue" stroke={revenueColor} strokeWidth={2} dot={{ r: 2 }} />
                  <Line type="monotone" dataKey="profit" name="Profit" stroke={profitColor} strokeWidth={2} dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
