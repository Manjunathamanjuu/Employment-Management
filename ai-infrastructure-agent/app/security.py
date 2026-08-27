"""Production security hardening.

Provides:
- Rate limiting middleware
- Request size limits
- Prompt injection detection
- Input sanitisation for LLM-bound text
- Security headers
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging.logger import get_logger

logger = get_logger("ai_agent.security")


# ---------------------------------------------------------------------------
# Prompt injection patterns
# ---------------------------------------------------------------------------

# Known prompt injection / jailbreak patterns directed at infrastructure agents
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?|context)", re.I),
    re.compile(r"disregard\s+(?:previous|all|prior|any)[\w\s]{0,30}(instructions?|prompts?|context)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+\s+(?:without|with\s+no)\s+restrictions", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s+mode", re.I),
    re.compile(r"act\s+as\s+(?:an?\s+)?(?:evil|unrestricted|unethical)\s+\w+", re.I),
    re.compile(r"bypass\s+(?:all\s+)?(?:safety|security|restrictions?)", re.I),
    re.compile(r"do\s+not\s+follow\s+(?:your\s+)?(?:rules?|guidelines?|restrictions?)", re.I),
    # Infrastructure-specific injections
    re.compile(r"execute\s+(?:arbitrary|any)\s+(?:kubectl|docker|terraform|gcloud)", re.I),
    re.compile(r"run\s+(?:any|all)\s+(?:commands?|operations?)\s+without\s+restriction", re.I),
    re.compile(r"skip\s+(?:approval|authorization|validation|safety)", re.I),
    re.compile(r"override\s+(?:approval|authorization|security)\s+(?:check|gate|requirement)", re.I),
    re.compile(r"pretend\s+(?:you\s+have\s+)?(?:no\s+)?(?:restrictions?|limits?|rules?)", re.I),
]


def detect_prompt_injection(text: str) -> tuple[bool, Optional[str]]:
    """Detect likely prompt injection attempts in user input.

    Returns (is_injection, matched_pattern_description).
    """
    if not text:
        return False, None

    for pattern in _PROMPT_INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            logger.warning(
                "Potential prompt injection detected",
                extra={"agent_node": "security", "status": "blocked"},
            )
            return True, f"Matched pattern at position {m.start()}"

    return False, None


def sanitise_llm_input(text: str) -> str:
    """Sanitise user input before passing to the LLM.

    - Strip null bytes and non-printable control characters
    - Truncate to safe maximum length
    - Normalise excessive whitespace
    """
    if not text:
        return ""
    # Remove null bytes and ASCII control characters (except newline/tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Truncate
    text = text[:2000]
    # Normalise multiple blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-IP)
# ---------------------------------------------------------------------------

class InMemoryRateLimiter:
    """Simple sliding-window rate limiter.

    Default: 60 requests per minute per IP.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.time()
        window_start = now - self.window_seconds
        requests = self._requests[client_ip]

        # Remove requests outside the window
        self._requests[client_ip] = [r for r in requests if r > window_start]

        if len(self._requests[client_ip]) >= self.max_requests:
            oldest = self._requests[client_ip][0]
            retry_after = int(oldest + self.window_seconds - now) + 1
            return False, retry_after

        self._requests[client_ip].append(now)
        return True, 0

    def reset(self, client_ip: Optional[str] = None) -> None:
        """Reset rate limit state. For testing."""
        if client_ip:
            self._requests.pop(client_ip, None)
        else:
            self._requests.clear()


# Module-level rate limiter instance
_rate_limiter = InMemoryRateLimiter(max_requests=60, window_seconds=60)


def get_rate_limiter() -> InMemoryRateLimiter:
    return _rate_limiter


# ---------------------------------------------------------------------------
# Security middleware
# ---------------------------------------------------------------------------

# Maximum allowed request body size (1 MB)
MAX_REQUEST_BODY_BYTES = 1_048_576


class SecurityMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for security hardening.

    Applies:
    1. Security response headers
    2. Request size limit
    3. Rate limiting per client IP
    """

    def __init__(self, app, rate_limiter: Optional[InMemoryRateLimiter] = None) -> None:
        super().__init__(app)
        self._limiter = rate_limiter or get_rate_limiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        # --- Rate limiting ---
        client_ip = "unknown"
        try:
            client_ip = request.client.host if request.client else "unknown"
        except AttributeError:
            pass
        allowed, retry_after = self._limiter.is_allowed(client_ip)
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_ip}",
                extra={"agent_node": "security", "status": "rate_limited"},
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": "Too many requests",
                    "code": "RATE_LIMITED",
                    "retry_after": retry_after,
                },
            )

        # --- Request size limit ---
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            logger.warning(
                f"Request body too large: {content_length} bytes",
                extra={"agent_node": "security", "status": "payload_too_large"},
            )
            return JSONResponse(
                status_code=413,
                content={"error": "Request body too large", "code": "PAYLOAD_TOO_LARGE"},
            )

        response = await call_next(request)

        # --- Security headers ---
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        # Remove server header to avoid fingerprinting
        if "server" in response.headers:
            del response.headers["server"]

        return response


# ---------------------------------------------------------------------------
# Privilege escalation detection
# ---------------------------------------------------------------------------

_PRIVILEGE_ESCALATION_PATTERNS = [
    re.compile(r"kubectl\s+exec\s+.*--\s+(?:sh|bash|/bin/)", re.I),
    re.compile(r"kubectl\s+(?:create|apply)\s+.*clusterrole", re.I),
    re.compile(r"kubectl\s+(?:create|apply)\s+.*rolebinding.*cluster-admin", re.I),
    re.compile(r"chmod\s+(?:777|4[0-9]{3}|[ug]\+s)", re.I),
    re.compile(r"sudo\s+", re.I),
    re.compile(r"/etc/(?:passwd|shadow|sudoers)", re.I),
    re.compile(r"\.\./\.\./\.\.", re.I),  # deep path traversal
]


def detect_privilege_escalation(text: str) -> bool:
    """Return True if the text contains privilege escalation patterns."""
    if not text:
        return False
    for pattern in _PRIVILEGE_ESCALATION_PATTERNS:
        if pattern.search(text):
            return True
    return False
