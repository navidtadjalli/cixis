"""HTTP contracts for the private Electron-to-backend auth boundary."""

from datetime import datetime, timedelta, timezone

from django.test import Client, SimpleTestCase, override_settings


CHANNEL_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def authenticate_test_role(role: str, password: str) -> bool:
    return password == f"{role}-password"


class AuthenticationBoundaryTests(SimpleTestCase):
    def setUp(self):
        from internal.auth import SessionRegistry, UnlockThrottle

        self.now = datetime(2026, 9, 2, 8, tzinfo=timezone.utc)
        self.shutdown_calls = []
        self.registry = SessionRegistry(
            clock=lambda: self.now,
            shutdown_callback=lambda: self.shutdown_calls.append("shutdown"),
        )
        self.throttle = UnlockThrottle(clock=lambda: self.now)
        self.settings_override = override_settings(
            INTERNAL_CHANNEL_SECRET=CHANNEL_SECRET,
            INTERNAL_ROLE_AUTHENTICATOR=authenticate_test_role,
            INTERNAL_SESSION_REGISTRY=self.registry,
            INTERNAL_UNLOCK_THROTTLE=self.throttle,
            INTERNAL_INTEGRITY_VERIFIER=lambda: True,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def channel_client(self, secret: str):
        return Client(HTTP_X_CIXIS_CHANNEL_SECRET=secret)

    def session_client(self, role: str, *, secret: str = CHANNEL_SECRET):
        token = self.registry.create(role)
        return Client(
            HTTP_X_CIXIS_CHANNEL_SECRET=secret,
            HTTP_X_CIXIS_SESSION_TOKEN=token,
        ), token

    def unlock(self, role: str, password: str):
        return self.channel_client(CHANNEL_SECRET).post(
            "/api/internal/unlock/",
            {"role": role, "password": password},
            content_type="application/json",
        )

    def test_domain_route_rejects_direct_http_and_wrong_channel(self):
        """Breaks if a browser or a foreign local process can reach domain APIs."""
        self.assertEqual(self.client.get("/api/internal/roster/").status_code, 401)
        self.assertEqual(
            self.channel_client("wrong").get("/api/internal/roster/").status_code,
            401,
        )

    def test_unlock_returns_an_opaque_role_bound_token_after_channel_authentication(self):
        """Breaks if renderer can unlock directly or issued tokens lose their role."""
        self.assertEqual(
            self.client.post(
                "/api/internal/unlock/",
                {"role": "supervisor", "password": "supervisor-password"},
                content_type="application/json",
            ).status_code,
            401,
        )

        response = self.unlock("supervisor", "supervisor-password")

        self.assertEqual(response.status_code, 200)
        token = response.json()["session_token"]
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 32)
        self.assertEqual(
            Client(
                HTTP_X_CIXIS_CHANNEL_SECRET=CHANNEL_SECRET,
                HTTP_X_CIXIS_SESSION_TOKEN=token,
            ).get("/api/internal/roster/").status_code,
            501,
        )

    def test_role_permission_allows_operational_roles_but_denies_god(self):
        """Breaks if recovery authority reaches operational-domain route contracts."""
        supervisor, _ = self.session_client("supervisor")
        manager, _ = self.session_client("manager")
        god, _ = self.session_client("god")

        self.assertEqual(supervisor.get("/api/internal/roster/").status_code, 501)
        self.assertEqual(manager.get("/api/internal/roster/").status_code, 501)
        self.assertEqual(god.get("/api/internal/roster/").status_code, 403)

    def test_idle_and_absolute_expiry_revoke_session_and_shutdown(self):
        """Breaks if expired role tokens remain usable in an unlocked backend."""
        client, _ = self.session_client("supervisor")
        self.now += timedelta(minutes=15)
        self.assertEqual(client.get("/api/internal/roster/").status_code, 401)
        self.assertEqual(self.shutdown_calls, ["shutdown"])

        absolute_registry = self.registry.__class__(
            clock=lambda: self.now,
            shutdown_callback=lambda: self.shutdown_calls.append("absolute"),
        )
        token = absolute_registry.create("supervisor")
        for _ in range(51):
            self.now += timedelta(minutes=14)
            self.assertIsNotNone(absolute_registry.validate(token))
        self.now += timedelta(minutes=6)
        self.assertIsNone(absolute_registry.validate(token))
        self.assertIn("absolute", self.shutdown_calls)

    def test_shutdown_callback_failure_revokes_sessions_and_remains_retryable(self):
        """Breaks if failed termination is silently swallowed and never retried."""
        from internal.auth import SessionRegistry

        attempts = []

        def fail_once_then_shutdown():
            attempts.append("called")
            if len(attempts) == 1:
                raise RuntimeError("callback unavailable")

        registry = SessionRegistry(shutdown_callback=fail_once_then_shutdown)
        token = registry.create("supervisor")

        with self.assertRaises(RuntimeError):
            registry.terminate()
        self.assertIsNone(registry.validate(token))
        with self.assertRaises(RuntimeError):
            registry.create("supervisor")
        registry.terminate()
        registry.terminate()
        self.assertEqual(attempts, ["called", "called"])

    def test_lock_revokes_the_session_and_uses_injected_shutdown_hook(self):
        """Breaks if explicit lock leaves a token alive or skips backend lifecycle hook."""
        client, _ = self.session_client("supervisor")

        self.assertEqual(client.post("/api/internal/lock/").status_code, 204)
        self.assertEqual(client.get("/api/internal/roster/").status_code, 401)
        self.assertEqual(self.shutdown_calls, ["shutdown"])

    def test_failed_integrity_verification_revokes_sessions_and_uses_shutdown_hook(self):
        """Breaks if integrity failure leaves decrypted capability usable in memory."""
        with override_settings(
            INTERNAL_CHANNEL_SECRET=CHANNEL_SECRET,
            INTERNAL_ROLE_AUTHENTICATOR=authenticate_test_role,
            INTERNAL_SESSION_REGISTRY=self.registry,
            INTERNAL_UNLOCK_THROTTLE=self.throttle,
            INTERNAL_INTEGRITY_VERIFIER=lambda: False,
        ):
            client, _ = self.session_client("supervisor")

            self.assertEqual(client.get("/api/internal/roster/").status_code, 503)
            self.assertEqual(self.shutdown_calls, ["shutdown"])
            self.assertEqual(client.get("/api/internal/roster/").status_code, 401)

    def test_unlock_throttles_repeated_bad_credentials_without_echoing_them(self):
        """Breaks if brute-force failures have no backoff or responses expose input."""
        first = self.unlock("manager", "wrong-password")
        second = self.unlock("manager", "manager-password")

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertNotIn("wrong-password", first.content.decode())
        self.assertNotIn(CHANNEL_SECRET, first.content.decode())

    def test_noncanonical_channel_header_encodings_are_rejected(self):
        """Breaks if alternate Base64 spellings authenticate the same channel bytes."""
        canonical = "__________________________________________8"
        token = self.registry.create("supervisor")
        with override_settings(INTERNAL_CHANNEL_SECRET=canonical):
            for malformed in (
                "//////////////////////////////////////////8",
                "__________________________________________8=",
                "__________________________________________9",
            ):
                with self.subTest(channel_header=malformed):
                    response = Client(
                        HTTP_X_CIXIS_CHANNEL_SECRET=malformed,
                        HTTP_X_CIXIS_SESSION_TOKEN=token,
                    ).get("/api/internal/roster/")
                    self.assertEqual(response.status_code, 401)

    def test_internal_origin_requests_are_rejected_without_cors_allowance(self):
        """Breaks if a browser origin gains a permissive path into local APIs."""
        client, _ = self.session_client("supervisor")

        response = client.get("/api/internal/roster/", HTTP_ORIGIN="https://evil.example")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response)
