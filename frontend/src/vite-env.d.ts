/// <reference types="vite/client" />

interface Window {
  cixis?: {
    platform: string;
    minimize: () => void;
    toggleMaximize: () => void;
    close: () => void;
  };
}
