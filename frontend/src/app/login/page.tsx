"use client";

/**
 * Login page — public route (no auth required).
 * Redirects to `?next=` param or /dashboard after successful login.
 */

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(username, password);
      const next = searchParams.get("next") || "/dashboard";
      // Prevent open-redirect: only allow relative paths
      const safeNext = next.startsWith("/") ? next : "/dashboard";
      router.replace(safeNext);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Login failed. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="osce-login-page">
      <form onSubmit={handleSubmit} className="osce-login-form" aria-label="Login">
        <h1>OSCE Platform Login</h1>

        {error && (
          <div className="osce-alert osce-alert--error" role="alert">
            {error}
          </div>
        )}

        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={submitting}
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
        />

        <button type="submit" disabled={submitting} className="osce-btn-primary">
          {submitting ? "Signing in…" : "Sign In"}
        </button>
      </form>
    </main>
  );
}
