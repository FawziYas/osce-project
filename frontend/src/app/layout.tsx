import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth/AuthContext";
import { ExaminerAssignmentProvider } from "@/lib/auth/ExaminerAssignmentContext";

export const metadata: Metadata = {
  title: "OSCE Platform",
  description: "Clinical examination management platform",
};

/**
 * Root layout — wraps the entire app with:
 *  1. AuthProvider — session check + user state
 *  2. ExaminerAssignmentProvider — station assignment state
 *
 * DepartmentScopeProvider is NOT mounted here — it is used per-route
 * layout (e.g. /departments/[deptId]/layout.tsx) because it requires
 * a specific deptId from the URL.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <ExaminerAssignmentProvider>
            {children}
          </ExaminerAssignmentProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
