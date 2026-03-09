"use client";

/**
 * ReportsDashboard — department-level reports.
 * Coordinator: own department only.
 * Admin / Superuser: all departments.
 * Examiner: ZERO access.
 */

import { usePermission } from "@/lib/auth";

interface DepartmentReport {
  department_id: number;
  department_name: string;
  total_exams: number;
  total_sessions: number;
  average_score: number | null;
}

interface Props {
  reports: DepartmentReport[];
  departmentId?: number;
}

export function ReportsDashboard({ reports, departmentId }: Props) {
  const { allowed: canView, loading } = usePermission("view", "report", departmentId);

  // Examiner ZERO access — no content in DOM
  if (loading || !canView) return null;

  if (reports.length === 0) {
    return (
      <section aria-label="Reports dashboard">
        <h2>Reports</h2>
        <p>No report data available.</p>
      </section>
    );
  }

  return (
    <section aria-label="Reports dashboard">
      <h2>Reports</h2>
      <table className="osce-reports-table">
        <thead>
          <tr>
            <th>Department</th>
            <th>Total Exams</th>
            <th>Total Sessions</th>
            <th>Average Score</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.department_id}>
              <td>{r.department_name}</td>
              <td>{r.total_exams}</td>
              <td>{r.total_sessions}</td>
              <td>
                {r.average_score !== null ? r.average_score.toFixed(1) : "N/A"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
