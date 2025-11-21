import { Badge } from "@/components/ui/badge"
import { OrderStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: OrderStatus | string
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const getStatusColor = (s: string) => {
    switch (s.toLowerCase()) {
      case OrderStatus.PENDING:
        return "bg-amber-100 text-amber-800 hover:bg-amber-200 border-amber-200"
      case OrderStatus.PROCESSED:
        return "bg-indigo-100 text-indigo-800 hover:bg-indigo-200 border-indigo-200"
      case OrderStatus.SHIPPED:
        return "bg-green-100 text-green-800 hover:bg-green-200 border-green-200"
      case OrderStatus.CANCELLED:
        return "bg-red-100 text-red-800 hover:bg-red-200 border-red-200"
      default:
        return "bg-gray-100 text-gray-800 hover:bg-gray-200 border-gray-200"
    }
  }

  return (
    <Badge variant="outline" className={cn("capitalize font-medium", getStatusColor(status), className)}>
      {status}
    </Badge>
  )
}
