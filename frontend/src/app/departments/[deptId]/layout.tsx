"use client";

/**
 * Department-scoped layout — wraps all /departments/[deptId]/* routes
 * with the DepartmentScopeProvider.
 *
 * This ensures that:
 *  1. The department is loaded and validated
 *  2. Non-global users can only access their own department
 *  3. All nested components can use useDepartmentScope()
 */

import { useParams } from "next/navigation";
import { DepartmentScopeProvider } from "@/lib/auth/DepartmentScopeContext";

export default function DepartmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const deptId = params?.deptId;

  if (!deptId) return null;

  return (
    <DepartmentScopeProvider deptId={Array.isArray(deptId) ? deptId[0] : deptId}>
      {children}
    </DepartmentScopeProvider>
  );
}
