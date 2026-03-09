/**
 * 401 Unauthorized page.
 * Shown when a user's session has expired or they are not logged in.
 */

import Link from "next/link";

export default function UnauthorizedPage() {
  return (
    <main className="osce-error-page">
      <h1>401 — Unauthorized</h1>
      <p>Your session has expired or you are not logged in.</p>
      <Link href="/login" className="osce-btn-primary">
        Go to Login
      </Link>
    </main>
  );
}
