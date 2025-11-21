import { redirect } from 'next/navigation';

export default function CatalogPage() {
  // Canonical customer catalog lives at /customer/catalog
  redirect('/customer/catalog');
}
