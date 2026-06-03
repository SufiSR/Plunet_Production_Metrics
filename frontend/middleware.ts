import { NextRequest, NextResponse } from "next/server";

/**
 * Protects /admin/* and /admin_legacy/* routes by checking for the signed session cookie issued
 * by the backend (`dora_session`). The API remains authoritative for admin
 * routes; this middleware only avoids a flash of protected content.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  const loginPath = `${basePath}/admin/login`;
  const normalizedPath =
    basePath && pathname.startsWith(basePath)
      ? pathname.slice(basePath.length) || "/"
      : pathname;

  // Allow login page through unconditionally
  if (normalizedPath === "/admin/login" || normalizedPath === "/admin_legacy/login") {
    return NextResponse.next();
  }

  // Must match backend SessionMiddleware session_cookie (see app/main.py: dora_session).
  const sessionCookie = request.cookies.get("dora_session");
  if (!sessionCookie?.value) {
    const nextPath = `${basePath}${normalizedPath === "/" ? "" : normalizedPath}`;
    const loginUrl = new URL(loginPath, request.url);
    loginUrl.searchParams.set("next", nextPath || "/");
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/admin_legacy/:path*"],
};
