import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"

export function ProductCardSkeleton() {
  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <Skeleton className="h-6 w-3/4 mb-2" />
        <Skeleton className="h-4 w-1/2" />
      </CardHeader>
      <CardContent className="flex-grow">
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </CardContent>
      <CardFooter className="pt-2 flex justify-between items-center">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-9 w-24" />
      </CardFooter>
    </Card>
  )
}

export function CatalogSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {Array.from({ length: 8 }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  )
}

export function TableRowSkeleton({ cells = 5 }: { cells?: number }) {
  return (
    <TableRow>
      {Array.from({ length: cells }).map((_, i) => (
        <TableCell key={i}>
          <Skeleton className="h-6 w-full" />
        </TableCell>
      ))}
    </TableRow>
  )
}

export function TableSkeleton({ rows = 5, cells = 5 }: { rows?: number; cells?: number }) {
  return (
    <Table>
      <TableBody>
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowSkeleton key={i} cells={cells} />
        ))}
      </TableBody>
    </Table>
  )
}

export function TableRowsSkeleton({ rows = 5, cells = 5 }: { rows?: number; cells?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <TableRowSkeleton key={i} cells={cells} />
      ))}
    </>
  )
}
