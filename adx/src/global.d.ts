export {};

declare global {
  interface Window {
    App?: {
      isLogin?: string | number;
      userKey?: string;
    };
    deHeaderS?: string;
  }
}
