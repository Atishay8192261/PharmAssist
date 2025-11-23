"use client";
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { AdminDashboardStats } from '@/lib/types';

const fetcher = (): Promise<AdminDashboardStats> => api.getAdminDashboardStats();

export function useDashboardStats() {
  const { data, error, isLoading, mutate } = useSWR('admin-dashboard-stats', fetcher, {
    revalidateOnFocus: true,
    refreshInterval: 60000, // background refresh every 60s
    dedupingInterval: 5000,
  });
  return {
    stats: data,
    loading: isLoading,
    error: error as any,
    refresh: () => mutate(),
  };
}
