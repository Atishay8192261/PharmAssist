"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { AIInventory } from "@/components/admin/ai-inventory"
import { ManualInventoryForm } from "@/components/admin/manual-inventory-form"
import { CreateSkuPanel } from "@/components/admin/create-sku-modal"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface LastAddedSummary {
  batch_id: number
  sku_name: string
  batch_no: string
  expiry_date: string
  quantity_on_hand: number
  cost_price?: number
  message?: string
}

export default function InventoryManagementPage() {
  const [lastAdded, setLastAdded] = useState<LastAddedSummary | null>(null)
  const [mode, setMode] = useState<"manual" | "ai" | "create">("manual")

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Inventory Management</h1>
        <Button variant="outline" asChild>
          <Link href="/admin/inventory/view">Go to Inventory View</Link>
        </Button>
      </div>
      {lastAdded && (
        <Card>
          <CardContent className="py-4 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline">Last Added</Badge>
              <span className="font-medium">{lastAdded.sku_name}</span>
              <span className="text-xs font-mono">{lastAdded.batch_no}</span>
            </div>
            <div className="text-sm text-muted-foreground flex flex-wrap gap-4">
              <span>Qty: {lastAdded.quantity_on_hand}</span>
              <span>Expiry: {lastAdded.expiry_date}</span>
              {lastAdded.cost_price !== undefined && <span>Cost: ${lastAdded.cost_price?.toFixed(2)}</span>}
              {lastAdded.message && <span className="italic">{lastAdded.message}</span>}
            </div>
          </CardContent>
        </Card>
      )}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Choose action:</span>
          <Select value={mode} onValueChange={(v) => setMode(v as any)}>
            <SelectTrigger className="w-[260px]">
              <SelectValue placeholder="Select action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="manual">Manual Inventory Add</SelectItem>
              <SelectItem value="ai">AI Inventory Add</SelectItem>
              <SelectItem value="create">Create Product & SKU</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="mt-4">
        {mode === "manual" && (
          <ManualInventoryForm onAdded={(summary) => setLastAdded(summary)} />
        )}
        {mode === "ai" && (
          <AIInventory onAdded={(r) => setLastAdded({
            batch_id: r.batch_id,
            sku_name: `SKU ${r.sku_id}`,
            batch_no: r.batch_no,
            expiry_date: r.expiry_date,
            quantity_on_hand: r.new_quantity_on_hand,
            message: r.message,
          })} />
        )}
        {mode === "create" && (
          <CreateSkuPanel onCreated={(sku) => {
            setLastAdded({
              batch_id: 0,
              sku_name: sku.label,
              batch_no: "",
              expiry_date: "",
              quantity_on_hand: 0,
              message: `SKU ${sku.sku_id} created`,
            })
          }} />
        )}
      </div>
    </div>
  )
}
