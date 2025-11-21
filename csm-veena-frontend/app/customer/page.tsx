"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { QuantityInput } from "@/components/shared/quantity-input"

export default function CustomerLanding() {
  const router = useRouter()
  const [search, setSearch] = useState("")
  const [previewQty, setPreviewQty] = useState(1)

  const goToCatalog = (e: React.FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams()
    if (search.trim()) params.set("search", search.trim())
    if (previewQty > 1) params.set("quantity", String(previewQty))
    router.push(`/customer/catalog?${params.toString()}`)
  }

  return (
    <div className="flex flex-col items-center text-center gap-10">
      <div className="space-y-4 max-w-2xl">
        <h1 className="text-4xl font-bold tracking-tight">Welcome to PharmAssist</h1>
        <p className="text-muted-foreground text-lg">
          Fast procurement and smart inventory insights for pharmacies & hospitals. Search the catalog or browse all products.
        </p>
      </div>
      <form onSubmit={goToCatalog} className="w-full max-w-xl flex flex-col gap-4">
        <div className="flex gap-3 items-center">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search a medicine (e.g. Amoxicillin)"
            className="flex-1 rounded-md border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <div className="flex items-center gap-2 bg-muted p-2 rounded-md">
            <span className="text-xs font-medium">Preview Qty:</span>
            <div className="w-20"><QuantityInput value={previewQty} onChange={setPreviewQty} min={1} max={1000} /></div>
          </div>
        </div>
        <div className="flex justify-center gap-4">
          <Button type="submit">Search Catalog</Button>
          <Button type="button" variant="secondary" onClick={() => router.push("/customer/catalog")}>Browse All</Button>
        </div>
      </form>
    </div>
  )
}
