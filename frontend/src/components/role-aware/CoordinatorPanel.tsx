"use client";

/**
 * CoordinatorPanel — shows coordinator management for a department.
 * Visible to: Coordinator (own dept) + Admin + Superuser.
 */

import { usePermission } from "@/lib/auth";
import { useDepartmentScope } from "@/lib/auth/DepartmentScopeContext";

interface Coordinator {
  id: number;
  full_name: string;
  position: string;
}

interface Props {
  coordinators: Coordinator[];
  onAdd?: () => void;
  onRemove?: (id: number) => void;
}

export function CoordinatorPanel({ coordinators, onAdd, onRemove }: Props) {
  const { departmentId } = useDepartmentScope();
  const { allowed: canView } = usePermission("list", "coordinator", departmentId);
  const { allowed: canEdit } = usePermission("create", "coordinator", departmentId);

  if (!canView) return null;

  return (
    <section aria-label="Coordinator panel">
      <h3>Coordinators</h3>

      {canEdit && onAdd && (
        <button onClick={onAdd} aria-label="Add coordinator">
          Add Coordinator
        </button>
      )}

      <ul className="osce-coord-list">
        {coordinators.map((c) => (
          <li key={c.id}>
            <span>{c.full_name}</span>
            <span className="osce-coord-pos">{c.position}</span>
            {canEdit && onRemove && (
              <button
                onClick={() => onRemove(c.id)}
                aria-label={`Remove ${c.full_name}`}
                className="osce-btn-danger"
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
