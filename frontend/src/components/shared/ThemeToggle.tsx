"use client";

import { setTheme, THEMES, useTheme } from "@/lib/theme";

import styles from "./themeToggle.module.css";

/** Compact LIGHT / DARK switch; the choice is remembered in this browser. */
export function ThemeToggle() {
  const theme = useTheme();
  return (
    <div className={styles.toggle} role="group" aria-label="Color theme">
      {[...THEMES].reverse().map((option) => (
        <button key={option} type="button" data-option={option} aria-pressed={theme === option} onClick={() => setTheme(option)}>
          {option}
        </button>
      ))}
    </div>
  );
}
