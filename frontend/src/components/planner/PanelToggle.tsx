"use client";

import styles from "./planner.module.css";

interface Props {
  open: boolean;
  controls: string;
  onToggle: () => void;
}

/** Tab on the map's right edge that retracts or restores the details column beside it. */
export function PanelToggle({ open, controls, onToggle }: Props) {
  return (
    <button
      type="button"
      className={styles.panelToggle}
      aria-expanded={open}
      aria-controls={controls}
      aria-label={open ? "Hide details" : "Show details"}
      onClick={onToggle}
    >
      <span aria-hidden>{open ? "›" : "‹"}</span>
      <span className={styles.panelToggleLabel}>Details</span>
    </button>
  );
}
