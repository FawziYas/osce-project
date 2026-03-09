"use client";

/**
 * StationList — lists stations.
 * Examiner sees ONLY assigned stations.
 * Coordinator sees all in their department.
 */

import { useAuth, usePermission } from "@/lib/auth";
import { useExaminerAssignment } from "@/lib/auth/ExaminerAssignmentContext";
import { isExaminer } from "@/lib/auth/roles";

interface Station {
  id: string;
  name: string;
  station_number: number;
}

interface Props {
  stations: Station[];
  departmentId?: number;
}

export function StationList({ stations, departmentId }: Props) {
  const { user } = useAuth();
  const { isAssigned } = useExaminerAssignment();
  const { allowed: canList } = usePermission("list", "station", departmentId);

  if (!canList || !user) return null;

  // Filter for examiners: show only assigned stations
  const visible = isExaminer(user.role)
    ? stations.filter((s) => isAssigned(s.id))
    : stations;

  if (visible.length === 0) {
    return (
      <section aria-label="Station list">
        <p>No stations available.</p>
      </section>
    );
  }

  return (
    <section aria-label="Station list">
      <h2>Stations</h2>
      <ul className="osce-station-list">
        {visible.map((station) => (
          <li key={station.id}>
            <a href={`/stations/${station.id}`}>
              Station {station.station_number}: {station.name}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
