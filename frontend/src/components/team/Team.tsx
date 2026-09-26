import { TEAM } from "@/content/team";

import { SiteNav } from "../shared/SiteNav";
import styles from "./team.module.css";

export function Team() {
  return (
    <main className={styles.page}>
      <SiteNav />
      <section className={`frame guides ${styles.hero}`}>
        <p className="eyebrow" data-gust="0">
          Team
        </p>
        <h1 className={`display ${styles.title}`} data-gust="1">
          The people behind <em>GridLock.</em>
        </h1>
      </section>
      <section className={`frame rule-top ${styles.members}`} aria-label="Team members" data-gust="2">
        {TEAM.length === 0 ? (
          <p className={`mono ${styles.empty}`}>Team members will be listed here.</p>
        ) : (
          <ul className={styles.grid}>
            {TEAM.map((member) => (
              <li key={member.name} className={styles.member}>
                <h2 className={`display ${styles.name}`}>{member.name}</h2>
                <p className="mono">{member.role}</p>
                {member.links && member.links.length > 0 && (
                  <p className={styles.links}>
                    {member.links.map((link) => (
                      <a key={link.href} href={link.href} target="_blank" rel="noreferrer" className="mono">
                        {link.label} <span aria-hidden>↗</span>
                      </a>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
