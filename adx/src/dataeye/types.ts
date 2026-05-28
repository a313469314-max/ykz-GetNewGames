export interface DataEyeNewProduct {
  productId: string | number;
  productName?: string;
  productIcon?: string;
  firstSeen?: string;
  type?: number | string;
}

export interface DataEyeNewProductDay {
  statDate: string;
  productNum?: number;
  products?: DataEyeNewProduct[];
}

export interface DataEyeResponseEnvelope<T> {
  code?: number | string;
  statusCode?: number | string;
  msg?: string;
  message?: string;
  data?: T;
  result?: T;
  rows?: T;
  list?: T;
  content?: T;
  success?: boolean;
}

export interface AppAuthSnapshot {
  isLogin: string | null;
  userKey: string | null;
  deHeaderS?: string | null;
}

export interface FetchDailyNewGamesResult {
  loginValid: boolean;
  days: DataEyeNewProductDay[];
}

export interface NormalizedNewGame {
  statDate: string;
  productId: string;
  productName: string;
  productIcon: string;
  stableProductIcon: string;
  firstSeen: string;
  type: number | string;
  platformName: string;
  detailUrl: string;
  fetchedAt: string;
}
