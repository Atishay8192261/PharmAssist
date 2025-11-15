'use client';

import { useRouter } from 'next/navigation';
import { getCurrentUser, removeToken } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Package, ShoppingBag, User, LogOut } from 'lucide-react';
import Link from 'next/link';

interface CustomerLayoutProps {
  children: React.ReactNode;
}

export function CustomerLayout({ children }: CustomerLayoutProps) {
  const router = useRouter();
  const user = getCurrentUser();

  const handleLogout = () => {
    removeToken();
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-muted/40">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/catalog" className="flex items-center gap-2 font-semibold text-lg">
              <Package className="h-6 w-6" />
              PharmAssist
            </Link>
            <nav className="hidden md:flex items-center gap-6">
              <Link
                href="/catalog"
                className="text-sm font-medium transition-colors hover:text-primary"
              >
                <div className="flex items-center gap-2">
                  <ShoppingBag className="h-4 w-4" />
                  Catalog
                </div>
              </Link>
              <Link
                href="/my-orders"
                className="text-sm font-medium transition-colors hover:text-primary"
              >
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  My Orders
                </div>
              </Link>
            </nav>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <User className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                <div className="flex flex-col">
                  <span>{user?.username}</span>
                  <span className="text-xs font-normal text-muted-foreground">Customer</span>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main className="container py-8">{children}</main>
    </div>
  );
}
