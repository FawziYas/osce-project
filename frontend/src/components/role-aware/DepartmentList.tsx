"use client";

/**
 * DepartmentList — renders a list of all departments.
 * Visible ONLY to Admin / Superuser roles.
 */

import { usePermission } from "@/lib/auth";

interface Department {
  id: number;
  name: string;
  code: string;
}

interface Props {
  departments: Department[];
}

export function DepartmentList({ departments }: Props) {
  const { allowed, loading } = usePermission("list", "department");

  // Zero-trust: never enter DOM if not allowed
  if (loading || !allowed) return null;

  return (
    <section aria-label="Department list">
      <h2>Departments</h2>
      <ul className="osce-dept-list">
        {departments.map((dept) => (
          <li key={dept.id}>
            <a href={`/departments/${dept.id}`}>
              {dept.name} ({dept.code})
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
