import { NextRequest, NextResponse } from "next/server";

/**
 * Protects /admin/* routes by checking for the existence of the backend
 * session cookie. The backend (FastAPI SessionMiddleware) is the authoritative
 * guard — a 401 from the API will redirect to login. This middleware provides
 * a fast UX redirect before a full page load.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page through unconditionally
  if (pathname === "/admin/login") {
    return NextResponse.next();
  }

  // All other /admin/* paths require a session cookie
  const sessionCookie = request.cookies.get("session");
  if (!sessionCookie?.value) {
    const loginUrl = new URL("/admin/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
