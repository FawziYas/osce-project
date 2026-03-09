"use client";

/**
 * StationCard — shows station details with role-aware actions.
 * "Edit": Coordinator + Admin + Superuser.
 * "Score": Examiner (assigned + active session only).
 */

import { usePermission } from "@/lib/auth";

interface Station {
  id: string;
  name: string;
  station_number: number;
  session_status?: "active" | "draft" | "completed";
}

interface Props {
  station: Station;
  departmentId?: number;
  onEdit?: (id: string) => void;
  onScore?: (id: string) => void;
}

export function StationCard({ station, departmentId, onEdit, onScore }: Props) {
  const { allowed: canView } = usePermission("view", "station", station.id);
  const { allowed: canEdit } = usePermission("edit", "station", departmentId);
  const { allowed: canScore } = usePermission("score", "station", station.id);

  if (!canView) return null;

  const isActive = station.session_status === "active";

  return (
    <article className="osce-station-card" aria-label={`Station ${station.station_number}: ${station.name}`}>
      <h3>
        Station {station.station_number}: {station.name}
      </h3>

      {canEdit && onEdit && (
        <button
          onClick={() => onEdit(station.id)}
          aria-label={`Edit ${station.name}`}
        >
          Edit
        </button>
      )}

      {/* Score button: only for assigned examiner AND only when session is active */}
      {canScore && isActive && onScore && (
        <button
          onClick={() => onScore(station.id)}
          aria-label={`Score ${station.name}`}
          className="osce-btn-primary"
        >
          Score
        </button>
      )}
    </article>
  );
}
