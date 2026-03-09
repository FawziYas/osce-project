"use client";

/**
 * CourseCard — shows a course with edit/delete controls.
 * Edit/Delete: Coordinator (own dept) + Admin + Superuser.
 */

import { usePermission } from "@/lib/auth";

interface Course {
  id: number;
  name: string;
  code: string;
}

interface Props {
  course: Course;
  departmentId: number;
  onEdit?: (id: number) => void;
  onDelete?: (id: number) => void;
}

export function CourseCard({ course, departmentId, onEdit, onDelete }: Props) {
  const { allowed: canView } = usePermission("view", "course", departmentId);
  const { allowed: canEdit } = usePermission("edit", "course", departmentId);
  const { allowed: canDelete } = usePermission("delete", "course", departmentId);

  if (!canView) return null;

  return (
    <article className="osce-course-card" aria-label={`Course: ${course.name}`}>
      <h3>{course.name}</h3>
      <span className="osce-course-code">{course.code}</span>

      {canEdit && onEdit && (
        <button
          onClick={() => onEdit(course.id)}
          aria-label={`Edit ${course.name}`}
        >
          Edit
        </button>
      )}
      {canDelete && onDelete && (
        <button
          onClick={() => onDelete(course.id)}
          aria-label={`Delete ${course.name}`}
          className="osce-btn-danger"
        >
          Delete
        </button>
      )}
    </article>
  );
}
