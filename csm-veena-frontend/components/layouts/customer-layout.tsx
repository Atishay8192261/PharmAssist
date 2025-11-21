"use client"

import type React from "react"

import { usePathname } from "next/navigation"
import { useAuth } from "@/context/auth-context"
import { useCart } from "@/context/cart-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Package, ShoppingBag, User, LogOut, ShoppingCart } from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

interface CustomerLayoutProps {
  children: React.ReactNode
}

export function CustomerLayout({ children }: CustomerLayoutProps) {
  const { user, logout } = useAuth()
  const { cartCount } = useCart()
  const pathname = usePathname()

  return (
    <div className="min-h-screen bg-muted/40">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto w-full max-w-[1480px] px-4 flex h-16 items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/catalog" className="flex items-center gap-2 font-semibold text-lg">
              <Package className="h-6 w-6" />
              PharmAssist
            </Link>
            <nav className="hidden md:flex items-center gap-6">
              <Link
                href="/catalog"
                className={cn(
                  "text-sm font-medium transition-colors hover:text-primary",
                  pathname === "/catalog" ? "text-primary" : "text-muted-foreground",
                )}
              >
                <div className="flex items-center gap-2">
                  <ShoppingBag className="h-4 w-4" />
                  Catalog
                </div>
              </Link>
              <Link
                href="/my-orders"
                className={cn(
                  "text-sm font-medium transition-colors hover:text-primary",
                  pathname === "/my-orders" ? "text-primary" : "text-muted-foreground",
                )}
              >
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  My Orders
                </div>
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <Link href="/cart">
              <Button variant="ghost" size="icon" className="relative">
                <ShoppingCart className="h-5 w-5" />
                {cartCount > 0 && (
                  <Badge
                    variant="destructive"
                    className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center rounded-full p-0 text-xs"
                  >
                    {cartCount}
                  </Badge>
                )}
              </Button>
            </Link>

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
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1480px] px-4 py-10 pb-20">{children}</main>
    </div>
  )
}
