"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

interface CreateSkuModalProps {
  onCreated?: (sku: { sku_id: number; label: string }) => void;
}

export function CreateSkuPanel({ onCreated }: CreateSkuModalProps) {
  const [step, setStep] = useState<"product" | "sku">("product");
  const [loading, setLoading] = useState(false);
  const [productId, setProductId] = useState<number | null>(null);

  // Product fields
  const [name, setName] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [description, setDescription] = useState("");

  // SKU fields
  const [packageSize, setPackageSize] = useState("");
  const [unitType, setUnitType] = useState("tablet");
  const [basePrice, setBasePrice] = useState<number | "">("");

  const resetAll = () => {
    setStep("product");
    setLoading(false);
    setProductId(null);
    setName("");
    setManufacturer("");
    setDescription("");
    setPackageSize("");
    setUnitType("tablet");
    setBasePrice("");
  };

  const createProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) {
      toast.error("Name required");
      return;
    }
    setLoading(true);
    try {
      const res = await api.createProduct({ name, manufacturer, description });
      setProductId(res.product_id);
      toast.success("Product created");
      setStep("sku");
    } catch (err: unknown) {
      let msg = 'Could not create product';
      if (err && typeof err === 'object' && 'message' in err) {
        msg = String((err as { message?: unknown }).message || msg);
      }
      toast.error("Failed", { description: msg });
    } finally {
      setLoading(false);
    }
  };

  const createSku = async (e: React.FormEvent) => {
    e.preventDefault();
    if (productId == null || !packageSize || !unitType || basePrice === "") {
      toast.error("All SKU fields required");
      return;
    }
    setLoading(true);
    try {
      const res = await api.createSku({
        product_id: productId,
        package_size: packageSize.trim(),
        unit_type: unitType.trim(),
        base_price: typeof basePrice === "string" ? parseFloat(basePrice) : basePrice,
      });
      toast.success("SKU created");
      onCreated?.({ sku_id: res.sku_id, label: `${name} ${packageSize}` });
      resetAll();
    } catch (err: unknown) {
      let msg = 'Could not create SKU';
      if (err && typeof err === 'object' && 'message' in err) {
        msg = String((err as { message?: unknown }).message || msg);
      }
      toast.error("Failed", { description: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Product & SKU</CardTitle>
        <CardDescription>{step === "product" ? "Step 1: Create product" : "Step 2: Create SKU for product"}</CardDescription>
      </CardHeader>
      <CardContent>
        {step === "product" && (
          <form onSubmit={createProduct} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="prod_name">Product Name</Label>
              <Input id="prod_name" value={name} onChange={(e) => setName(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="manufacturer">Manufacturer</Label>
              <Input id="manufacturer" value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} disabled={loading} />
            </div>
            <Button type="submit" disabled={loading || !name} className="w-full">
              {loading ? "Creating..." : "Create Product"}
            </Button>
          </form>
        )}
        {step === "sku" && (
          <form onSubmit={createSku} className="space-y-4">
            <div className="space-y-2">
              <Label>Product ID</Label>
              <Input value={productId ?? ''} disabled readOnly />
            </div>
            <div className="space-y-2">
              <Label htmlFor="package_size">Package Size</Label>
              <Input id="package_size" value={packageSize} onChange={(e) => setPackageSize(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unit_type">Unit Type</Label>
              <Input id="unit_type" value={unitType} onChange={(e) => setUnitType(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="base_price">Base Price</Label>
              <Input id="base_price" type="number" min={0} step={0.01} value={basePrice} onChange={(e) => setBasePrice(e.target.value === '' ? '' : parseFloat(e.target.value))} required disabled={loading} />
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={resetAll} disabled={loading}>Reset</Button>
              <Button type="submit" disabled={loading || productId == null} className="flex-1">
                {loading ? "Creating..." : "Create SKU"}
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
