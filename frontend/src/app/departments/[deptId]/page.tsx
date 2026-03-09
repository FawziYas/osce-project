"use client";

/**
 * Department detail page — shows department info, courses, coordinators.
 * Protected: Admin + Superuser + Coordinators (own dept).
 */

import { useDepartmentScope } from "@/lib/auth/DepartmentScopeContext";

export default function DepartmentDetailPage() {
  const { department } = useDepartmentScope();

  return (
    <main>
      <h1>{department.name}</h1>
      <p>Department ID: {department.id}</p>
      {/* Nested role-aware components go here:
          <CoordinatorPanel />
          <CourseCard /> list
          etc.
      */}
    </main>
  );
}
