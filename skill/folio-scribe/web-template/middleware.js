import { next } from "@vercel/functions";

const REALM = "Folio Scribe";

function unauthorized() {
  return new Response("Authentication required\n", {
    status: 401,
    headers: {
      "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`,
      "Cache-Control": "no-store, max-age=0",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
    },
  });
}

function decodeBasicAuth(header) {
  if (!header || !header.startsWith("Basic ")) {
    return null;
  }

  try {
    const decoded = atob(header.slice(6));
    const separator = decoded.indexOf(":");
    if (separator < 0) {
      return null;
    }
    return {
      user: decoded.slice(0, separator),
      password: decoded.slice(separator + 1),
    };
  } catch {
    return null;
  }
}

function sameValue(left, right) {
  if (left.length !== right.length) {
    return false;
  }

  let result = 0;
  for (let index = 0; index < left.length; index += 1) {
    result |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return result === 0;
}

export default function middleware(request) {
  const expectedUser = process.env.FOLIO_SCRIBE_WEB_USER || "grefer";
  const expectedPassword = process.env.FOLIO_SCRIBE_WEB_PASSWORD || "";

  if (!expectedPassword) {
    return unauthorized();
  }

  const credentials = decodeBasicAuth(request.headers.get("authorization"));
  if (!credentials) {
    return unauthorized();
  }

  if (!sameValue(credentials.user, expectedUser) || !sameValue(credentials.password, expectedPassword)) {
    return unauthorized();
  }

  return next();
}

export const config = {
  matcher: "/(.*)",
};
