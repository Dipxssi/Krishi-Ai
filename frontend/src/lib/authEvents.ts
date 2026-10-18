const listeners = new Set<() => void>();

export function subscribeAuth(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

export function notifyAuthChanged(): void {
  listeners.forEach((listener) => listener());
}
