'use client';

import { useState } from 'react';
import { apiClient, AddInventoryNLPResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Lightbulb } from 'lucide-react';

const EXAMPLE_PROMPTS = [
  'Add 20 units of Amoxicillin 250mg 100-bottle Batch #AMOX-NEW expiring Dec 2030',
  'Add 5 units of Paracetamol 500mg 10-strip Batch #P500-ZZ1 expiring January 2029',
  'Add 15 units of Ibuprofen 400mg 20-strip Batch #IBU400-A1 expiring March 2028',
];

export function AIInventory() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AddInventoryNLPResponse | null>(null);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await apiClient.addInventoryNLP({ text });
      setResult(response);
      setText('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add inventory');
    } finally {
      setLoading(false);
    }
  };

  const useExample = (example: string) => {
    setText(example);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">AI Inventory Management</h1>
        <p className="text-muted-foreground mt-2">
          Add inventory using natural language descriptions
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Add Inventory</CardTitle>
              <CardDescription>
                Describe the inventory item in natural language
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="inventory-text">Inventory Description</Label>
                  <Textarea
                    id="inventory-text"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="e.g., Add 10 units of Aspirin 100mg 50-strip Batch #ASP-001 expiring June 2029"
                    rows={4}
                    required
                    disabled={loading}
                  />
                </div>

                <Button type="submit" disabled={loading || !text.trim()} className="w-full">
                  {loading ? 'Processing...' : 'Parse & Add Inventory'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-yellow-600" />
                <CardTitle className="text-lg">Example Prompts</CardTitle>
              </div>
              <CardDescription>
                Click an example to use it
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {EXAMPLE_PROMPTS.map((prompt, index) => (
                <button
                  key={index}
                  onClick={() => useExample(prompt)}
                  className="w-full text-left p-3 text-sm rounded-lg border bg-muted/50 hover:bg-muted transition-colors"
                  type="button"
                >
                  {prompt}
                </button>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result && (
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {result.message}
              </AlertDescription>
            </Alert>
          )}

          {result && (
            <Card>
              <CardHeader>
                <CardTitle>Inventory Added</CardTitle>
                <CardDescription>Details of the newly added inventory</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Batch ID</p>
                    <p className="font-semibold">{result.batch_id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">SKU ID</p>
                    <p className="font-semibold">{result.sku_id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Batch Number</p>
                    <p className="font-semibold">{result.batch_no}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Quantity Added</p>
                    <p className="font-semibold">{result.quantity_added}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">New Quantity on Hand</p>
                    <p className="font-semibold">{result.new_quantity_on_hand}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Expiry Date</p>
                    <p className="font-semibold">
                      {new Date(result.expiry_date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div>
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                    Powered by {result.source}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
