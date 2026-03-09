"use client";

/**
 * SessionPanel — shows session details and assignment controls.
 * "Assign Path/Examiner": Coordinator + Admin + Superuser.
 */

import { usePermission } from "@/lib/auth";

interface Session {
  id: string;
  name: string;
  date: string;
  status: "draft" | "active" | "completed";
}

interface Props {
  session: Session;
  departmentId: number;
  onAssign?: (sessionId: string) => void;
}

export function SessionPanel({ session, departmentId, onAssign }: Props) {
  const { allowed: canView } = usePermission("view", "session", departmentId);
  const { allowed: canAssign } = usePermission("assign", "session", departmentId);

  if (!canView) return null;

  return (
    <article className="osce-session-panel" aria-label={`Session: ${session.name}`}>
      <h3>{session.name}</h3>
      <time dateTime={session.date}>{session.date}</time>
      <span className={`osce-session-status osce-session-status--${session.status}`}>
        {session.status}
      </span>

      {canAssign && onAssign && (
        <button
          onClick={() => onAssign(session.id)}
          aria-label={`Assign paths/examiners for ${session.name}`}
        >
          Assign Path / Examiner
        </button>
      )}
    </article>
  );
}
