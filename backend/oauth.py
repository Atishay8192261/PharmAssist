import os, json, base64, hashlib, secrets, requests
from flask import request, jsonify

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_TOKEN_INFO = "https://oauth2.googleapis.com/tokeninfo"

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def register_oauth(app):
    """Register OAuth2 related endpoints (Google Authorization Code + PKCE exchange).

    Frontend Flow (SPA / Next.js):
      1. Generate code_verifier (random 64 bytes base64url) & code_challenge = BASE64URL(SHA256(verifier)).
      2. Redirect user to Google with client_id, redirect_uri, response_type=code, scope, code_challenge & method=S256, state.
      3. Google redirects back to frontend callback route with code & state.
      4. Frontend POSTs code + code_verifier to /api/oauth/google/exchange.
      5. Backend exchanges code for tokens, verifies id_token, upserts user/customer, returns JWT.
    """

    @app.post("/api/oauth/google/exchange")
    def google_oauth_exchange():
        try:
            body = request.get_json(force=True) or {}
            code = body.get("code")
            code_verifier = body.get("code_verifier")
            if not code or not code_verifier:
                return jsonify({"error": "Missing code or code_verifier"}), 400

            client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
            if not (client_id and client_secret and redirect_uri):
                return jsonify({"error": "OAuth2 not fully configured"}), 500

            # Exchange authorization code for tokens
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
            token_resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=15)
            if token_resp.status_code != 200:
                return jsonify({"error": "Token exchange failed", "details": token_resp.text}), 400
            token_json = token_resp.json()
            id_token = token_json.get("id_token")
            access_token = token_json.get("access_token")
            if not id_token:
                return jsonify({"error": "Missing id_token in response"}), 400

            # Verify id_token via tokeninfo endpoint (signature + audience)
            info_resp = requests.get(GOOGLE_TOKEN_INFO, params={"id_token": id_token}, timeout=10)
            if info_resp.status_code != 200:
                return jsonify({"error": "id_token verification failed", "details": info_resp.text}), 400
            info = info_resp.json()
            if info.get("aud") != client_id:
                return jsonify({"error": "Invalid audience"}), 400
            email = info.get("email")
            email_verified = info.get("email_verified") == "true"
            name = info.get("name") or email
            if not email or not email_verified:
                return jsonify({"error": "Email missing or not verified"}), 400

            # Determine role: admin if exact match or domain match
            admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
            admin_domain = os.getenv("ADMIN_EMAIL_DOMAIN", "").lower().strip()
            role = "customer"
            if email.lower() in admin_emails or (admin_domain and email.lower().endswith("@" + admin_domain)):
                role = "admin"

            from .db import get_connection, reset_pool
            import bcrypt
            from psycopg import sql as _sql

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Lookup existing user by email mapped to username (we use email as username for OAuth)
                        cur.execute("SELECT user_id, role, customer_id FROM Users WHERE username = %s LIMIT 1", (email,))
                        row = cur.fetchone()
                        if not row:
                            # If customer role, create customer record first
                            customer_id = None
                            if role == "customer":
                                cust_type = os.getenv("OAUTH_AUTO_CUSTOMER_TYPE", "Pharmacy")
                                cur.execute(
                                    "INSERT INTO Customers(name, address, customer_type) VALUES (%s, %s, %s) RETURNING customer_id",
                                    (name[:255], None, cust_type),
                                )
                                customer_id = int(cur.fetchone()[0])
                            # Store placeholder password hash (random) since login will be OAuth only
                            placeholder_pw = secrets.token_urlsafe(12)
                            hashed = bcrypt.hashpw(placeholder_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                            cur.execute(
                                "INSERT INTO Users(customer_id, username, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING user_id, customer_id",
                                (customer_id, email, hashed, role),
                            )
                            urow = cur.fetchone()
                            user_id = int(urow[0]); customer_id = urow[1]
                        else:
                            user_id = int(row[0]); role_db = row[1]; customer_id = row[2]
                            # Upgrade role to admin if newly qualifies
                            if role == "admin" and role_db != "admin":
                                cur.execute("UPDATE Users SET role='admin' WHERE user_id=%s", (user_id,))
                        conn.commit()
                        return user_id, role, customer_id

            try:
                user_id, final_role, customer_id = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try: reset_pool()
                    except Exception: pass
                    user_id, final_role, customer_id = _work()
                else:
                    return jsonify({"error": msg}), 400

            # Issue local JWT
            from .app import _make_access_token  # reuse helper
            jwt_token = _make_access_token({
                "sub": str(user_id),
                "username": email,
                "role": final_role,
                "customer_id": int(customer_id) if customer_id is not None else None,
                "auth_provider": "google_oauth",
            })

            return jsonify({
                "access_token": jwt_token,
                "token_type": "Bearer",
                "provider": "google",
                "email": email,
                "role": final_role,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 400
