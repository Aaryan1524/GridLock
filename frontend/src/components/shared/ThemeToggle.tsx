"use client";

import type { ReactNode } from "react";

import { setTheme, type Theme, useTheme } from "@/lib/theme";

import styles from "./themeToggle.module.css";

const OPTIONS: { theme: Theme; label: string; icon: ReactNode }[] = [
  {
    theme: "light",
    label: "Light theme",
    icon: (
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
        <circle cx="8" cy="8" r="3" />
        <path d="M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15M3.05 3.05l1.13 1.13M11.82 11.82l1.13 1.13M3.05 12.95l1.13-1.13M11.82 4.18l1.13-1.13" />
      </svg>
    ),
  },
  {
    theme: "dark",
    label: "Dark theme",
    icon: (
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
        <path d="M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1Z" />
      </svg>
    ),
  },
];

/** Sun / moon switch; the choice is remembered in this browser. */
export function ThemeToggle() {
  const theme = useTheme();
  return (
    <div className={styles.toggle} role="group" aria-label="Color theme">
      {OPTIONS.map((option) => (
        <button
          key={option.theme}
          type="button"
          data-option={option.theme}
          aria-label={option.label}
          title={option.label}
          aria-pressed={theme === option.theme}
          onClick={() => setTheme(option.theme)}
        >
          {option.icon}
        </button>
      ))}
    </div>
  );
}
