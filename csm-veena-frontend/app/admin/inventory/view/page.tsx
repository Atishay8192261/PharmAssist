"use client";

import { useState } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import { useInventory } from "@/hooks/useInventory";
import type { AdminInventoryResponse } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/shared/skeletons";
import { formatPrice, formatDate, getExpirySeverity } from "@/lib/utils";
import { toast } from "sonner";
import { Search, AlertTriangle, Pencil, Trash2, X, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function InventoryViewPage() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [page, setPage] = useState(1);
  const [filterServer, setFilterServer] = useState<string>("");
  const { inventory, total, totalPages, loading, error, refresh } = useInventory({ page, limit: 25, search: debouncedSearch, filter: filterServer });
  const [filter, setFilter] = useState<"all" | "low-stock" | "critical" | "expiring" | "recent">("all");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editQuantity, setEditQuantity] = useState<number | "">("");
  const [editExpiry, setEditExpiry] = useState<string>("");
  const [editCostPrice, setEditCostPrice] = useState<number | "">("");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  if (error) {
    const msg = (error as any)?.message || 'Failed to load inventory';
    toast.error("Error", { description: msg });
  }

  const beginEdit = (batch_id: number, quantity: number, expiry_date: string, cost_price: number) => {
    setEditingId(batch_id);
    setEditQuantity(quantity);
    setEditExpiry(expiry_date);
    setEditCostPrice(cost_price);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditQuantity("");
    setEditExpiry("");
  };

  const saveEdit = async () => {
    if (editingId == null) return;
    setSaving(true);
    try {
      // optimistic UI could be added later
      await import("@/lib/api").then(m => m.api.updateInventoryBatch(editingId, {
        quantity_on_hand: typeof editQuantity === "string" ? parseInt(editQuantity) : editQuantity,
        expiry_date: editExpiry,
        cost_price: typeof editCostPrice === "string" ? parseFloat(editCostPrice) : editCostPrice,
      }));
      toast.success("Batch updated");
      cancelEdit();
      refresh();
    } catch (err: unknown) {
      let msg = 'Could not update batch';
      if (err && typeof err === 'object' && 'message' in err) {
        msg = String((err as { message?: unknown }).message || msg);
      }
      toast.error("Update failed", { description: msg });
    } finally {
      setSaving(false);
    }
  };

  const deleteBatch = async (batch_id: number) => {
    if (!confirm("Delete this batch?")) return;
    setDeletingId(batch_id);
    try {
      await import("@/lib/api").then(m => m.api.deleteInventoryBatch(batch_id));
      toast.success("Batch deleted");
      refresh();
    } catch (err: unknown) {
      let msg = 'Could not delete batch';
      if (err && typeof err === 'object' && 'message' in err) {
        msg = String((err as { message?: unknown }).message || msg);
      }
      toast.error("Delete failed", { description: msg });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredBatches =
    inventory.filter((batch) => {
      const matchesSearch =
        batch.sku_name.toLowerCase().includes(search.toLowerCase()) ||
        batch.batch_no.toLowerCase().includes(search.toLowerCase());
      if (!matchesSearch) return false;
      if (filter === "low-stock") return batch.quantity_on_hand < 10;
      if (filter === "critical") return batch.quantity_on_hand < 5;
      if (filter === "expiring") {
        const severity = getExpirySeverity(batch.expiry_date);
        return severity === "warn" || severity === "danger";
      }
      if (filter === "recent") {
        // Treat top 10 highest batch_id as recently added
        const topSorted = [...inventory]
          .sort((a, b) => b.batch_id - a.batch_id)
          .slice(0, 10)
          .map(b => b.batch_id);
        return topSorted.includes(batch.batch_id);
      }
      return true;
    }) || [];

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">Inventory View</h1>
        <Card>
          <CardContent className="p-6">
            <TableSkeleton rows={10} cells={7} />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Inventory View</h1>
        <div className="flex items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search SKU or Batch..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <Badge
          variant={filter === "all" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setFilter("all")}
        >
          All Batches
        </Badge>
        <Badge
          variant={filter === "low-stock" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => { setFilter("low-stock"); setFilterServer("low-stock"); setPage(1); }}
        >
          Low Stock
        </Badge>
        <Badge
          variant={filter === "critical" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => { setFilter("critical"); setFilterServer("critical"); setPage(1); }}
        >
          Critical Stock
        </Badge>
        <Badge
          variant={filter === "expiring" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => { setFilter("expiring"); setFilterServer("expiring"); setPage(1); }}
        >
          Expiring Soon
        </Badge>
        <Badge
          variant={filter === "recent" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => { setFilter("recent"); setFilterServer("recent"); setPage(1); }}
        >
          Recently Added
        </Badge>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU Name</TableHead>
                <TableHead>Batch No</TableHead>
                <TableHead>Expiry Date</TableHead>
                <TableHead>Quantity</TableHead>
                <TableHead className="text-right">Cost Price</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredBatches.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    No inventory batches found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredBatches.map((batch) => {
                  const severity = getExpirySeverity(batch.expiry_date);
                  const isEditing = editingId === batch.batch_id;
                  return (
                    <TableRow key={batch.batch_id}>
                      <TableCell className="font-medium">{batch.sku_name}</TableCell>
                      <TableCell className="font-mono text-xs">{batch.batch_no}</TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            type="date"
                            value={editExpiry}
                            onChange={(e) => setEditExpiry(e.target.value)}
                            className="h-8"
                          />
                        ) : (
                          <div className="flex items-center gap-2">
                            {formatDate(batch.expiry_date)}
                            {severity !== "normal" && (
                              <AlertTriangle
                                className={cn("h-4 w-4", severity === "danger" ? "text-red-500" : "text-amber-500")}
                              />
                            )}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            type="number"
                            min={0}
                            value={editQuantity}
                            onChange={(e) => setEditQuantity(e.target.value ? parseInt(e.target.value) : "")}
                            className="h-8 w-24"
                          />
                        ) : (
                          batch.quantity_on_hand
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {isEditing ? (
                          <Input
                            type="number"
                            min={0}
                            step={0.01}
                            value={editCostPrice}
                            onChange={(e) => setEditCostPrice(e.target.value ? parseFloat(e.target.value) : "")}
                            className="h-8 w-24 text-right"
                          />
                        ) : (
                          `$${formatPrice(batch.cost_price)}`
                        )}
                      </TableCell>
                      <TableCell>
                        {severity === "danger" && <Badge variant="destructive">Critical</Badge>}
                        {severity === "warn" && (
                          <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                            Warning
                          </Badge>
                        )}
                        {severity === "normal" && <Badge variant="outline">OK</Badge>}
                      </TableCell>
                      <TableCell className="text-right">
                        {isEditing ? (
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="secondary" onClick={cancelEdit} disabled={saving}>
                              <X className="h-4 w-4" />
                            </Button>
                            <Button size="sm" onClick={saveEdit} disabled={saving || !editExpiry || editQuantity === ""}>
                              <Check className="h-4 w-4" />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => beginEdit(batch.batch_id, batch.quantity_on_hand, batch.expiry_date, batch.cost_price)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => deleteBatch(batch.batch_id)}
                              disabled={deletingId === batch.batch_id}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between p-4 border-t text-sm">
            <span>
              Page {page} of {totalPages} • {total} total
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
              <Button size="sm" variant="secondary" onClick={() => refresh()}>Refresh</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
