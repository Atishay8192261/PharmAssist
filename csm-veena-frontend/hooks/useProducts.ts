"use client";
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { ProductsResponse } from '@/lib/types';

interface Params {
  page?: number;
  limit?: number;
  quantity?: number;
  customer_id?: number;
  search?: string;
}

const fetcher = (key: string, params: Params): Promise<ProductsResponse> => {
  return api.getProducts({
    page: params.page,
    limit: params.limit,
    quantity: params.quantity,
    customer_id: params.customer_id,
    search: params.search,
  });
};

export function useProducts(params: Params) {
  const { data, error, isLoading, mutate } = useSWR(['products', params], ([, p]) => fetcher('products', p), {
    keepPreviousData: true,
    revalidateOnFocus: true,
    dedupingInterval: 3000,
  });
  return {
    products: data?.items || [],
    meta: data,
    loading: isLoading,
    error: error as any,
    refresh: () => mutate(),
  };
}
