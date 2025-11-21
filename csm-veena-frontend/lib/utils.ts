import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(price: number | string | undefined | null): string {
  const num = typeof price === "string" ? Number.parseFloat(price) : price
  if (num === undefined || num === null || isNaN(num)) return "0.00"
  return num.toFixed(2)
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return value
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value)
    return isNaN(parsed) ? 0 : parsed
  }
  return 0
}

export type ExpirySeverity = "normal" | "warn" | "danger"

export function getExpirySeverity(dateISO: string | null | undefined): ExpirySeverity {
  if (!dateISO) return "normal"

  const expiry = new Date(dateISO)
  const now = new Date()
  const diffTime = expiry.getTime() - now.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays < 7) return "danger"
  if (diffDays < 30) return "warn"
  return "normal"
}

export function formatDate(date: string | Date): string {
  if (!date) return ""
  const d = new Date(date)
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function formatDateTime(date: string | Date): string {
  if (!date) return ""
  const d = new Date(date)
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
