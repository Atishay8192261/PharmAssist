import { formatPrice } from "@/lib/utils"
import { cn } from "@/lib/utils"

interface PriceTagProps {
  basePrice: number
  effectivePrice: number
  className?: string
  size?: "sm" | "md" | "lg"
}

export function PriceTag({ basePrice, effectivePrice, className, size = "md" }: PriceTagProps) {
  const hasDiscount = effectivePrice < basePrice

  const sizeClasses = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-lg font-semibold",
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {hasDiscount && (
        <span className={cn("text-muted-foreground line-through decoration-red-500/50", sizeClasses[size])}>
          ${formatPrice(basePrice)}
        </span>
      )}
      <span className={cn(hasDiscount ? "text-green-600 font-medium" : "text-foreground", sizeClasses[size])}>
        ${formatPrice(effectivePrice)}
      </span>
    </div>
  )
}
