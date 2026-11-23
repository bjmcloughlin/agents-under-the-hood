"""A throwaway token issuer for testing the server's auth on your own machine.

It stands in for a real identity provider (Entra ID, Auth0, Keycloak and so on):
it makes a signing key, serves the public half at /jwks.json, and prints tokens
signed with the private half. The key lives in memory and is gone when you stop it.
Never use this for anything real.

    uv run python scripts/local_issuer.py
"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

PORT = 9000
ISSUER = f"http://localhost:{PORT}"
AUDIENCE = "http://localhost:8080/mcp"
KEY_ID = "local-test-key"

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
jwk.update(kid=KEY_ID, use="sig", alg="RS256")


def mint(audience=AUDIENCE, scope="books.read", lifetime=3600) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": audience,
        "sub": "test-user",
        "client_id": "local-test-client",
        "scope": scope,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": KEY_ID})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/jwks.json":
            self.send_error(404)
            return
        body = json.dumps({"keys": [jwk]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    tokens = {
        "GOOD": mint(),
        "WRONG_AUDIENCE": mint(audience="http://localhost:8080/some-other-server"),
        "NO_SCOPE": mint(scope=""),
        "EXPIRED": mint(lifetime=-60),
    }
    for name, token in tokens.items():
        print(f"export {name}={token}")
    print(f"# serving signing keys at {ISSUER}/jwks.json, Ctrl+C to stop", flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
