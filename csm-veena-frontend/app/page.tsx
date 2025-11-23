"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function HomePage() {
  return (
    <main className="min-h-[70vh] flex flex-col items-center justify-center text-center px-6 py-16 space-y-10 bg-gradient-to-b from-white to-muted/30">
      <div className="space-y-4 max-w-2xl">
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">Pharma Assist</h1>
        <p className="text-lg md:text-xl text-muted-foreground leading-relaxed">
          Empowering pharmacies and hospitals with intelligent inventory, fair pricing, and fast fulfillment. We streamline procurement,
          reduce expiries through FEFO batch management, and surface real-time insights so you can focus on patient care.
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-4">
        <Button asChild size="lg">
          <Link href="/login">Login</Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href="/customer/catalog">Browse Catalog</Link>
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full pt-8">
        <div className="p-5 rounded-lg border bg-background shadow-sm">
          <h2 className="font-semibold mb-2">Smart Inventory</h2>
          <p className="text-sm text-muted-foreground">AI-assisted batch ingestion plus FEFO-based checkout minimizes waste and stockouts.</p>
        </div>
        <div className="p-5 rounded-lg border bg-background shadow-sm">
          <h2 className="font-semibold mb-2">Dynamic Pricing</h2>
          <p className="text-sm text-muted-foreground">Customer & SKU specific discount rules ensure transparent, consistent margins.</p>
        </div>
        <div className="p-5 rounded-lg border bg-background shadow-sm">
          <h2 className="font-semibold mb-2">Actionable Analytics</h2>
          <p className="text-sm text-muted-foreground">Dashboard highlights expiring stock, low quantities, revenue and profit trends.</p>
        </div>
      </div>
    </main>
  )
}
