from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

REGISTER = {
    "username": "sara",
    "email": "sara@example.com",
    "password": "Str0ng-Pass-123",
    "password2": "Str0ng-Pass-123",
}


class AuthFlowTests(APITestCase):
    def register(self, **overrides):
        return self.client.post("/auth/register/", {**REGISTER, **overrides})

    def login(self, username="sara", password="Str0ng-Pass-123"):
        return self.client.post("/auth/login/", {"username": username, "password": password})

    def test_register_creates_user_and_hashes_password(self):
        r = self.register()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", r.data)
        user = User.objects.get(username="sara")
        self.assertNotEqual(user.password, REGISTER["password"])
        self.assertTrue(user.check_password(REGISTER["password"]))

    def test_register_password_mismatch(self):
        r = self.register(password2="different")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password2", r.data)

    def test_register_weak_password(self):
        r = self.register(password="12345678", password2="12345678")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.data)

    def test_register_duplicate_email(self):
        self.register()
        r = self.register(username="other")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.data)

    def test_login_returns_access_and_refresh(self):
        self.register()
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)

    def test_login_wrong_password(self):
        self.register()
        self.assertEqual(self.login(password="nope").status_code, 401)

    def test_me_requires_token(self):
        self.assertEqual(self.client.get("/auth/me/").status_code, 401)

    def test_me_with_token_and_update(self):
        self.register()
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        r = self.client.get("/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["username"], "sara")
        r = self.client.patch("/auth/me/", {"first_name": "Sara"})
        self.assertEqual(r.data["first_name"], "Sara")

    def test_refresh_gives_new_access_token(self):
        self.register()
        refresh = self.login().data["refresh"]
        r = self.client.post("/auth/token/refresh/", {"refresh": refresh})
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_logout_blacklists_refresh_token(self):
        self.register()
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        r = self.client.post("/auth/logout/", {"refresh": tokens["refresh"]})
        self.assertEqual(r.status_code, status.HTTP_205_RESET_CONTENT)
        # the blacklisted refresh token can no longer be used
        self.client.credentials()
        r = self.client.post("/auth/token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(r.status_code, 401)

    def test_garbage_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.token")
        self.assertEqual(self.client.get("/auth/me/").status_code, 401)