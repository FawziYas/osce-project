"use client";

/**
 * DepartmentCard — shows a department with edit/delete controls.
 * Edit/Delete buttons render ONLY for Admin / Superuser.
 */

import { usePermission } from "@/lib/auth";

interface Department {
  id: number;
  name: string;
  code: string;
}

interface Props {
  department: Department;
  onEdit?: (id: number) => void;
  onDelete?: (id: number) => void;
}

export function DepartmentCard({ department, onEdit, onDelete }: Props) {
  const { allowed: canView } = usePermission("view", "department");
  const { allowed: canEdit } = usePermission("edit", "department");
  const { allowed: canDelete } = usePermission("delete", "department");

  if (!canView) return null;

  return (
    <article className="osce-dept-card" aria-label={`Department: ${department.name}`}>
      <h3>{department.name}</h3>
      <span className="osce-dept-code">{department.code}</span>

      {/* Conditional rendering — never CSS display:none */}
      {canEdit && onEdit && (
        <button
          onClick={() => onEdit(department.id)}
          aria-label={`Edit ${department.name}`}
        >
          Edit
        </button>
      )}
      {canDelete && onDelete && (
        <button
          onClick={() => onDelete(department.id)}
          aria-label={`Delete ${department.name}`}
          className="osce-btn-danger"
        >
          Delete
        </button>
      )}
    </article>
  );
}
