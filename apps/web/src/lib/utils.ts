import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatEta(minutes: number): string {
  if (minutes < 0) return "Arrived";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const m = Math.round(minutes % 60);
  const h = Math.floor(minutes / 60);
  if (h < 24) return `${h} hr${h > 1 ? 's' : ''} ${m > 0 ? `${m} min` : ''}`.trim();
  const d = Math.floor(h / 24);
  const remainingHours = h % 24;
  return `${d} day${d > 1 ? 's' : ''} ${remainingHours > 0 ? `${remainingHours} hr${remainingHours > 1 ? 's' : ''}` : ''}`.trim();
}
