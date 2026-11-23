import logging
import os

import anyio
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

logger = logging.getLogger(__name__)

SCOPE = "books.read"
REQUIRED_ENV = ("MCP_AUTH_ISSUER", "MCP_AUTH_JWKS_URL", "MCP_AUTH_AUDIENCE", "MCP_PUBLIC_URL")


class JwtVerifier(TokenVerifier):
    """Checks a bearer token that some identity provider issued. This server never issues one."""

    def __init__(self, issuer: str, jwks_url: str, audience: str):
        self.issuer = issuer
        self.audience = audience
        # The provider's public signing keys, fetched once and cached
        self.keys = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def _decode(self, token: str) -> dict:
        key = self.keys.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],  # never read the algorithm from the token itself
            issuer=self.issuer,
            audience=self.audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            # The key fetch is a blocking HTTP call, so keep it off the event loop
            claims = await anyio.to_thread.run_sync(self._decode, token)
        except jwt.PyJWTError as e:
            logger.info("rejected token: %s", e)
            return None
        # Entra calls the claim scp, most other providers call it scope
        scopes = (claims.get("scp") or claims.get("scope") or "").split()
        return AccessToken(
            token=token,
            client_id=claims.get("azp") or claims.get("client_id") or "unknown",
            scopes=scopes,
            expires_at=claims["exp"],
            subject=claims["sub"],
        )


def from_env() -> tuple[AuthSettings, JwtVerifier]:
    """Builds the auth setup from the environment, and stops the process if any of it is missing."""
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"refusing to serve HTTP without auth: set {', '.join(missing)}")

    issuer = os.environ["MCP_AUTH_ISSUER"]
    settings = AuthSettings(
        issuer_url=issuer,
        resource_server_url=os.environ["MCP_PUBLIC_URL"],
        required_scopes=[SCOPE],
        # The verifier checks the audience itself
        validate_token_resource=False,
    )
    verifier = JwtVerifier(issuer, os.environ["MCP_AUTH_JWKS_URL"], os.environ["MCP_AUTH_AUDIENCE"])
    return settings, verifier
