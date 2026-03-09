"use client";

/**
 * ExamCard — shows an exam with edit/delete controls.
 * Edit: Coordinator (own dept) + Admin + Superuser.
 * Delete: Coordinator-Head (own dept) + Admin + Superuser.
 */

import { usePermission } from "@/lib/auth";

interface Exam {
  id: string;
  name: string;
  date: string;
  status: string;
}

interface Props {
  exam: Exam;
  departmentId: number;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
}

export function ExamCard({ exam, departmentId, onEdit, onDelete }: Props) {
  const { allowed: canView } = usePermission("view", "exam", departmentId);
  const { allowed: canEdit } = usePermission("edit", "exam", departmentId);
  const { allowed: canDelete } = usePermission("delete", "exam", departmentId);

  if (!canView) return null;

  return (
    <article className="osce-exam-card" aria-label={`Exam: ${exam.name}`}>
      <h3>{exam.name}</h3>
      <time dateTime={exam.date}>{exam.date}</time>
      <span className="osce-exam-status">{exam.status}</span>

      {canEdit && onEdit && (
        <button
          onClick={() => onEdit(exam.id)}
          aria-label={`Edit ${exam.name}`}
        >
          Edit
        </button>
      )}
      {canDelete && onDelete && (
        <button
          onClick={() => onDelete(exam.id)}
          aria-label={`Delete ${exam.name}`}
          className="osce-btn-danger"
        >
          Delete
        </button>
      )}
    </article>
  );
}
