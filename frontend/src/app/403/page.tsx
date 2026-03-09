/**
 * 403 Forbidden page.
 * Shown when a user is authenticated but lacks permission for the resource.
 */

import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <main className="osce-error-page">
      <h1>403 — Forbidden</h1>
      <p>You do not have permission to access this resource.</p>
      <p>
        If you believe this is an error, contact your department coordinator or
        system administrator.
      </p>
      <Link href="/dashboard" className="osce-btn-primary">
        Go to Dashboard
      </Link>
    </main>
  );
}
