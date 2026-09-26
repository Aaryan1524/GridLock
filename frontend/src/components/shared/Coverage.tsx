import type { Metadata, Metrics } from "@/lib/contract";
import { formatNumber, utilityName } from "@/lib/format";

/**
 * Location coverage, shown only from the backend's reconciled breakdown and always with its
 * denominator, so "located" and "not assessed" figures visibly add up.
 */
export function Coverage({ metadata, metrics }: { metadata: Metadata; metrics: Metrics }) {
  const r = metrics.resolution;
  const located = r.locatedAutomatically + r.locatedHumanVerifiedOnly;
  const notAssessed = r.notLocatedUnresolved + r.notLocatedNoNamedSite;
  const utilities = Object.keys(metrics.projectsByUtility).map((code) => utilityName(metadata, code));
  return (
    <div className="mono-plain" style={{ lineHeight: 1.8 }}>
      <div>
        Sources: {utilities.join(" + ")} public planning filings · OpenStreetMap geometry
      </div>
      <div>
        Of all {formatNumber(metrics.projects)} projects: {formatNumber(located)} located ({formatNumber(r.locatedAutomatically)}{" "}
        automatically, {formatNumber(r.locatedHumanVerifiedOnly)} via human-verified points) · {formatNumber(notAssessed)} not
        spatially assessed ({formatNumber(r.notLocatedUnresolved)} with sites not yet resolved, {formatNumber(r.notLocatedNoNamedSite)}{" "}
        name no site). Not assessed means unknown, not “no overlap”.
      </div>
    </div>
  );
}
