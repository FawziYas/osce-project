"use client";

/**
 * ExaminerAssignment — manage station-examiner assignments.
 * Visible to: Coordinator + Admin + Superuser.
 * NEVER visible to Examiner.
 */

import { usePermission } from "@/lib/auth";

interface Assignment {
  id: number;
  examiner_name: string;
  station_name: string;
  station_id: string;
}

interface Props {
  assignments: Assignment[];
  departmentId: number;
  onAssign?: () => void;
  onRemove?: (id: number) => void;
}

export function ExaminerAssignment({ assignments, departmentId, onAssign, onRemove }: Props) {
  const { allowed: canView } = usePermission("list", "assignment", departmentId);
  const { allowed: canCreate } = usePermission("create", "assignment", departmentId);
  const { allowed: canDelete } = usePermission("delete", "assignment", departmentId);

  // NEVER render for examiner — enforced by permission matrix
  if (!canView) return null;

  return (
    <section aria-label="Examiner assignments">
      <h3>Examiner Assignments</h3>

      {canCreate && onAssign && (
        <button onClick={onAssign} aria-label="Assign examiner to station">
          Assign Examiner
        </button>
      )}

      {assignments.length === 0 ? (
        <p>No assignments yet.</p>
      ) : (
        <table className="osce-assignment-table">
          <thead>
            <tr>
              <th>Examiner</th>
              <th>Station</th>
              {canDelete && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={a.id}>
                <td>{a.examiner_name}</td>
                <td>{a.station_name}</td>
                {canDelete && (
                  <td>
                    {onRemove && (
                      <button
                        onClick={() => onRemove(a.id)}
                        aria-label={`Remove assignment: ${a.examiner_name} from ${a.station_name}`}
                        className="osce-btn-danger"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
