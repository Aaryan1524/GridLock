"use client";

import { useSyncExternalStore } from "react";

import { DEFAULT_THEME, type Theme, THEME_STORAGE_KEY as STORAGE_KEY, THEMES } from "./themeScript";

// Light / dark theme. The theme lives on <html data-theme>, set before first paint by
// THEME_INIT_SCRIPT (see app/layout.tsx), so a stored choice never flashes the other theme.
// Dark is the default whenever nothing has been chosen.

export { type Theme, THEMES };

const CHANGE_EVENT = "gridlock:themechange";

export function currentTheme(): Theme {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const value = document.documentElement.dataset.theme;
  return (THEMES as readonly string[]).includes(value ?? "") ? (value as Theme) : DEFAULT_THEME;
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private windows can refuse storage; the theme still applies for this page.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** Calls back whenever the theme changes, here or in another tab. Returns the unsubscribe function. */
export function onThemeChange(callback: () => void): () => void {
  const fromStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return;
    const next = event.newValue === "light" || event.newValue === "dark" ? event.newValue : DEFAULT_THEME;
    if (next === currentTheme()) return;
    document.documentElement.dataset.theme = next;
    callback();
  };
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", fromStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", fromStorage);
  };
}

export function useTheme(): Theme {
  return useSyncExternalStore(onThemeChange, currentTheme, () => DEFAULT_THEME);
}
