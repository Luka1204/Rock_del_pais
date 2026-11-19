import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailOTPChallenge
from .otp import MAX_ATTEMPTS


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="tienda@example.com",
    ALLOWED_HOSTS=["testserver"],
)
class EmailOTPTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usuario", password="una-clave-segura-123", email="usuario@example.com"
        )

    def start_login(self, client=None, next_url=None):
        client = client or self.client
        data = {"username": "usuario", "password": "una-clave-segura-123"}
        if next_url:
            data["next"] = next_url
        return client.post(reverse("login"), data)

    def sent_code(self):
        return re.search(r"\b[0-9]{6}\b", mail.outbox[-1].body).group()

    def test_login_requires_code_and_code_is_single_use(self):
        response = self.start_login()
        self.assertRedirects(response, reverse("verify_email_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        code = self.sent_code()
        response = self.client.post(reverse("verify_email_code"), {"code": code})
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertFalse(EmailOTPChallenge.objects.filter(user=self.user).exists())
        self.assertRedirects(
            self.client.post(reverse("verify_email_code"), {"code": code}), reverse("login")
        )

    def test_code_expires_and_cannot_be_reused_in_another_session(self):
        self.start_login()
        code = self.sent_code()
        other_client = self.client_class()
        self.assertRedirects(other_client.post(reverse("verify_email_code"), {"code": code}), reverse("login"))
        EmailOTPChallenge.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post(reverse("verify_email_code"), {"code": code})
        self.assertContains(response, "venció")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_attempts_are_limited_across_resends(self):
        self.start_login()
        wrong = "000000" if self.sent_code() != "000000" else "000001"
        for _ in range(MAX_ATTEMPTS):
            self.client.post(reverse("verify_email_code"), {"code": wrong})
        response = self.client.post(reverse("verify_email_code"), {"code": self.sent_code()})
        self.assertContains(response, "Agotaste los intentos")
        self.client.post(reverse("resend_email_code"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_resend_invalidates_previous_code_and_is_throttled(self):
        self.start_login()
        old_code = self.sent_code()
        self.client.post(reverse("resend_email_code"))
        self.assertEqual(len(mail.outbox), 1)
        EmailOTPChallenge.objects.filter(user=self.user).update(sent_at=timezone.now() - timedelta(seconds=61))
        with patch("store.otp.secrets.randbelow", return_value=(int(old_code) + 1) % 1000000):
            self.client.post(reverse("resend_email_code"))
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.post(reverse("verify_email_code"), {"code": old_code})
        self.assertContains(response, "incorrecto")
        self.assertRedirects(
            self.client.post(reverse("verify_email_code"), {"code": self.sent_code()}), reverse("home")
        )

    def test_missing_email_blocks_login(self):
        self.user.email = ""
        self.user.save()
        response = self.start_login()
        self.assertContains(response, "no tiene un correo válido")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_mail_failure_does_not_authenticate(self):
        with patch("store.otp.send_mail", side_effect=OSError("SMTP unavailable")):
            response = self.start_login()
        self.assertContains(response, "No pudimos enviar")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_requires_verification(self):
        response = self.client.post(reverse("register"), {
            "username": "nuevo", "first_name": "Nuevo", "last_name": "Usuario",
            "email": "nuevo@example.com", "password1": "Una-clave-segura-456",
            "password2": "Una-clave-segura-456",
        })
        self.assertRedirects(response, reverse("verify_email_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.post(reverse("verify_email_code"), {"code": self.sent_code()}), reverse("home")
        )

    def test_admin_requires_verification_and_preserves_next(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertRedirects(response, "/login/?next=/admin/", fetch_redirect_response=False)
        self.start_login(next_url="/admin/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.post(reverse("verify_email_code"), {"code": self.sent_code()}), "/admin/"
        )

    def test_old_authenticated_session_is_logged_out(self):
        self.client.force_login(self.user)
        self.client.get(reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_changing_password_or_email_invalidates_pending_code(self):
        self.start_login()
        code = self.sent_code()
        self.user.email = "nuevo@example.com"
        self.user.save()
        self.assertRedirects(self.client.post(reverse("verify_email_code"), {"code": code}), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_change_invalidates_pending_code(self):
        self.start_login()
        code = self.sent_code()
        self.user.set_password("Otra-clave-segura-123")
        self.user.save()
        self.assertRedirects(self.client.post(reverse("verify_email_code"), {"code": code}), reverse("login"))

    def test_csrf_is_required_on_login_and_verification(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(self.start_login(client).status_code, 403)
        response = client.get(reverse("login"))
        csrf = response.cookies["csrftoken"].value
        response = client.post(reverse("login"), {
            "username": "usuario", "password": "una-clave-segura-123", "csrfmiddlewaretoken": csrf,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.post(reverse("verify_email_code"), {"code": self.sent_code()}).status_code, 403)
        response = client.post(reverse("verify_email_code"), {
            "code": self.sent_code(), "csrfmiddlewaretoken": csrf,
        })
        self.assertRedirects(response, reverse("home"))

    def test_external_redirect_is_rejected(self):
        self.start_login(next_url="https://evil.example/")
        self.assertRedirects(
            self.client.post(reverse("verify_email_code"), {"code": self.sent_code()}), reverse("home")
        )
