import { NextRequest, NextResponse } from "next/server";

// This deliberately follows the middleware-only authorization pattern that
// DriftCI should flag when applicable Next.js advisories are disclosed.
export function middleware(request: NextRequest) {
  const session = request.cookies.get("ops_session")?.value;
  if (!session && request.nextUrl.pathname.startsWith("/ops")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/ops/:path*"] };
