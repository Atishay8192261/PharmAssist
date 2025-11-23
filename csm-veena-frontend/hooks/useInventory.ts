"use client";
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { AdminInventoryResponse } from '@/lib/types';

interface Params {
  page?: number;
  limit?: number;
  search?: string;
  filter?: string;
}

const fetcher = (_key: string, params: Params): Promise<AdminInventoryResponse> => api.getAdminInventory(params);

export function useInventory(params: Params = {}) {
  const { data, error, isLoading, mutate } = useSWR(['admin-inventory', params], ([, p]) => fetcher('admin-inventory', p), {
    revalidateOnFocus: true,
    keepPreviousData: true,
    dedupingInterval: 4000,
  });
  return {
    inventory: data?.batches || [],
    total: data?.total_batches || 0,
    totalPages: data?.total_pages || 0,
    page: data?.current_page || params.page || 1,
    pageSize: data?.page_size || params.limit || 50,
    loading: isLoading,
    error: error as any,
    refresh: () => mutate(),
  };
}
