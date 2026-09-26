import Link from "next/link";

import styles from "./siteNav.module.css";
import { ThemeToggle } from "./ThemeToggle";

/** The one site header: identical on the landing page, the planner and the team page. */
export function SiteNav() {
  return (
    <header className={`frame ${styles.nav}`}>
      <Link href="/" className={styles.wordmark}>
        GridLock
      </Link>
      <nav className={styles.actions} aria-label="Site">
        <Link className="mono" href="/team">
          Team
        </Link>
        <ThemeToggle />
      </nav>
    </header>
  );
}
