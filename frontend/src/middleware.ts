/**
 * Next.js Edge Middleware — route protection at the CDN/edge level.
 *
 * Runs BEFORE any page component renders, using only the session cookie
 * and a lightweight /api/v2/session/ call to determine access.
 *
 * This is the first line of defence; withAuth() is the second.
 * Both exist because edge middleware cannot access React context.
 */

import { NextResponse, type NextRequest } from "next/server";
import { ROUTE_RULES } from "./lib/auth/routes";
import { hasRole as _hasRole } from "./lib/auth/roles";
import type { AuthUser, Role } from "./lib/auth/types";

// ── Paths that NEVER require auth ──────────────────────────────────

const PUBLIC_PATHS = ["/login", "/401", "/403", "/_next", "/favicon.ico", "/api"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
}

// ── Middleware ──────────────────────────────────────────────────────

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip public paths
  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  // ── 1. Session check ─────────────────────────────────────────
  const user = await getSessionUser(request);

  if (!user) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // ── 2. Route-rule check ──────────────────────────────────────
  const rule = matchPathnameToRule(pathname);

  if (rule) {
    // Superuser always passes role check
    if (user.role !== "SUPERUSER" && !rule.roles.includes(user.role)) {
      const forbiddenUrl = request.nextUrl.clone();
      forbiddenUrl.pathname = "/403";
      return NextResponse.redirect(forbiddenUrl);
    }
  }

  // All clear
  return NextResponse.next();
}

// ── Config ──────────────────────────────────────────────────────────

export const config = {
  matcher: [
    /*
     * Match all paths except:
     *  - _next/static, _next/image
     *  - favicon.ico
     *  - public assets
     */
    "/((?!_next/static|_next/image|favicon\\.ico|icons|images|manifest\\.json|sw\\.js).*)",
  ],
};

// ── Helpers ─────────────────────────────────────────────────────────

/**
 * Fetch the current user from the Django session endpoint.
 * Forwards the request's cookies so the backend can validate the session.
 */
async function getSessionUser(request: NextRequest): Promise<AuthUser | null> {
  try {
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

    const res = await fetch(`${apiBase}/api/v2/session/`, {
      headers: {
        Cookie: request.headers.get("cookie") || "",
        "X-Requested-With": "XMLHttpRequest",
      },
      // No caching in middleware — always fresh
      cache: "no-store",
    });

    if (!res.ok) return null;

    const data = await res.json();
    return data.user ?? null;
  } catch {
    return null;
  }
}

/**
 * Match a pathname against the static route rules.
 * Simple first-match — identical to the client-side matchRoute().
 */
function matchPathnameToRule(pathname: string) {
  for (const rule of ROUTE_RULES) {
    if (edgePathMatches(pathname, rule.pattern)) {
      return rule;
    }
  }
  return null;
}

/**
 * Lightweight path matcher for edge runtime (no full regex engine).
 */
function edgePathMatches(pathname: string, pattern: string): boolean {
  const pathParts = pathname.replace(/\/$/, "").split("/").filter(Boolean);
  const patternParts = pattern.replace(/\/$/, "").split("/").filter(Boolean);

  let pi = 0;
  let pati = 0;

  while (pi < pathParts.length && pati < patternParts.length) {
    const pat = patternParts[pati];
    if (pat.endsWith("*")) return true;
    if (pat.startsWith(":")) {
      pi++;
      pati++;
      continue;
    }
    if (pathParts[pi] !== pat) return false;
    pi++;
    pati++;
  }

  return pi === pathParts.length && pati === patternParts.length;
}
