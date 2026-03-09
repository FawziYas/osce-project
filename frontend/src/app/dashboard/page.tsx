"use client";

/**
 * Dashboard — landing page after login.
 * Protected: any authenticated user.
 */

import { useAuth, ROLES, COORDINATOR_ROLES, GLOBAL_ROLES } from "@/lib/auth";
import { withAuth } from "@/lib/auth/withAuth";

const ALL_ROLES = [...GLOBAL_ROLES, ...COORDINATOR_ROLES, ROLES.EXAMINER] as const;

function DashboardPage() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <main className="osce-dashboard">
      <header>
        <h1>OSCE Dashboard</h1>
        <div className="osce-user-info">
          <span>
            {user.full_name} ({user.role})
          </span>
          <button onClick={logout} className="osce-btn-secondary">
            Sign Out
          </button>
        </div>
      </header>

      <nav aria-label="Main navigation">
        <ul>
          {/* Department list — only global roles */}
          {(user.role === "SUPERUSER" || user.role === "ADMIN") && (
            <li>
              <a href="/departments">Departments</a>
            </li>
          )}

          {/* Own department — coordinators */}
          {user.department_id && (
            <li>
              <a href={`/departments/${user.department_id}`}>My Department</a>
            </li>
          )}

          {/* Scoring — examiners */}
          {user.role === "EXAMINER" && (
            <li>
              <a href="/stations">My Stations</a>
            </li>
          )}

          {/* Reports — everyone except examiner */}
          {user.role !== "EXAMINER" && (
            <li>
              <a href={user.department_id ? `/reports/department/${user.department_id}` : "/reports"}>
                Reports
              </a>
            </li>
          )}
        </ul>
      </nav>
    </main>
  );
}

export default withAuth([...ALL_ROLES])(DashboardPage);
