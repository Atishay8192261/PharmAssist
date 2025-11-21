"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useDebounce } from "@/hooks/use-debounce";

interface SkuOption { sku_id: number; label: string }

interface ManualAddedSummary {
  batch_id: number
  sku_name: string
  batch_no: string
  expiry_date: string
  quantity_on_hand: number
  cost_price: number
  message: string
}

export function ManualInventoryForm({ onAdded }: { onAdded?: (summary: ManualAddedSummary) => void }) {
  const [skuName, setSkuName] = useState("");
  const [batchNo, setBatchNo] = useState("");
  const [quantity, setQuantity] = useState<number | "">("");
  const [expiryDate, setExpiryDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [skuId, setSkuId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<SkuOption[]>([]);
  const [costPrice, setCostPrice] = useState<string>("");
  // const [searching, setSearching] = useState(false); // reserved for future loading indicator
  const debounced = useDebounce(query, 250);

  const reset = () => {
    setSkuName("");
    setBatchNo("");
    setQuantity("");
    setExpiryDate("");
    setSkuId(null);
    setOptions([]);
    setQuery("");
    setCostPrice("");
  };

  useEffect(() => {
    setQuery(skuName);
  }, [skuName]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (!debounced || debounced.length < 2) { setOptions([]); return; }
      // setSearching(true);
      try {
        const res = await api.getProducts({ search: debounced, limit: 10, quantity: 1 });
        if (!active) return;
        const opts = res.items.map((p) => ({ sku_id: p.sku_id, label: `${p.product_name} ${p.package_size}` }));
        setOptions(opts);
      } catch {
        if (active) setOptions([]);
      } finally {
        // if (active) setSearching(false);
      }
    };
    run();
    return () => { active = false };
  }, [debounced]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!skuName || !batchNo || !quantity || !expiryDate) {
      toast.error("Missing fields", { description: "Fill all fields." });
      return;
    }
    setLoading(true);
    try {
      const resp = await api.createInventoryBatch({
        sku_id: skuId ?? undefined,
        sku_name: skuId ? undefined : skuName.trim(),
        batch_no: batchNo.trim(),
        quantity: typeof quantity === "string" ? parseInt(quantity) : quantity,
        expiry_date: expiryDate,
        // Optional cost_price override
        ...(costPrice ? { cost_price: parseFloat(costPrice) } : {}),
      });
      if (resp && resp.batch) {
        toast.success("Inventory batch saved");
        onAdded?.({
          batch_id: resp.batch.batch_id,
          sku_name: resp.batch.sku_name,
          batch_no: resp.batch.batch_no,
          expiry_date: resp.batch.expiry_date,
          quantity_on_hand: resp.batch.quantity_on_hand,
          cost_price: resp.batch.cost_price,
          message: resp.message || 'Batch upserted'
        });
      } else {
        toast.success("Batch processed (no payload)");
      }
      reset();
    } catch (err: unknown) {
      let message = 'Could not save batch';
      if (err && typeof err === 'object' && 'message' in err) {
        message = String((err as { message?: unknown }).message || message);
      }
      toast.error("Failed", { description: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manual Inventory Add</CardTitle>
        <CardDescription>
          Directly create or increment a batch. Cost defaults to 60% of base price and can be edited later in Inventory View.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="sku_name">SKU (Product + package)</Label>
            <Input
              id="sku_name"
              placeholder="Type to search e.g. Paracetamol 500mg 10-strip"
              value={skuName}
              onChange={(e) => { setSkuName(e.target.value); setSkuId(null); }}
              disabled={loading}
              required
            />
            {options.length > 0 && (
              <div className="mt-2 border rounded-md max-h-48 overflow-auto">
                {options.map((opt) => (
                  <button
                    type="button"
                    key={opt.sku_id}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                    onClick={() => { setSkuName(opt.label); setSkuId(opt.sku_id); setOptions([]); }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Pick an existing SKU from suggestions. New SKUs cannot be created here.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="batch_no">Batch Number</Label>
            <Input
              id="batch_no"
              placeholder="P500-A3"
              value={batchNo}
              onChange={(e) => setBatchNo(e.target.value)}
              disabled={loading}
              required
            />
            <p className="text-xs text-muted-foreground">Must be unique per SKU; reusing increments quantity.</p>
          </div>
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="quantity">Quantity</Label>
              <Input
                id="quantity"
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value ? parseInt(e.target.value) : "")}
                disabled={loading}
                required
              />
              <p className="text-xs text-muted-foreground">Must be a positive integer.</p>
            </div>
            <div className="flex-1 space-y-2">
              <Label htmlFor="expiry_date">Expiry Date</Label>
              <Input
                id="expiry_date"
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
                disabled={loading}
                required
              />
              <p className="text-xs text-muted-foreground">Format: YYYY-MM-DD.</p>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cost_price">Cost Price (optional)</Label>
            <Input
              id="cost_price"
              type="number"
              step="0.01"
              min={0}
              placeholder="e.g. 0.55"
              value={costPrice}
              onChange={(e) => setCostPrice(e.target.value)}
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">Override default 60% heuristic. Leave blank to auto-calc.</p>
          </div>
          <Button type="submit" disabled={loading || !skuName || !batchNo || !quantity || !expiryDate} className="w-full">
            {loading ? "Saving..." : "Save Batch"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
