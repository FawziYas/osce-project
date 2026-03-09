"use client";

/**
 * PathView — shows exam path (circuit) details.
 * Visible to: Coordinator (own dept) + Admin + Superuser.
 * NEVER visible to Examiner.
 */

import { usePermission } from "@/lib/auth";

interface Path {
  id: string;
  name: string;
  station_count: number;
}

interface Props {
  path: Path;
  departmentId: number;
}

export function PathView({ path, departmentId }: Props) {
  const { allowed: canView } = usePermission("view", "path", departmentId);

  // Examiner NEVER sees paths — enforced by usePermission matrix
  if (!canView) return null;

  return (
    <article className="osce-path-view" aria-label={`Path: ${path.name}`}>
      <h3>{path.name}</h3>
      <p>Stations: {path.station_count}</p>
    </article>
  );
}
