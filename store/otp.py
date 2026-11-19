import logging
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import EmailOTPChallenge

logger = logging.getLogger(__name__)
OTP_LIFETIME = timedelta(minutes=10)
RESEND_INTERVAL = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def code_digest(user_id, token, code):
    return salted_hmac(
        "store.email_otp", f"{user_id}:{token}:{code}", algorithm="sha256"
    ).hexdigest()


def valid_email(user):
    try:
        validate_email(user.email)
    except ValidationError:
        return False
    return True


def issue_code(user, token):
    if not valid_email(user):
        return "missing_email"
    if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and (
        not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or not settings.DEFAULT_FROM_EMAIL
    ):
        logger.error("SMTP email credentials or sender are not configured")
        return "email_error"

    now = timezone.now()
    code = f"{secrets.randbelow(1000000):06d}"
    with transaction.atomic():
        # Locking the user serializes issuance even when no challenge exists yet.
        type(user).objects.select_for_update().get(pk=user.pk)
        challenge = EmailOTPChallenge.objects.filter(user=user).first()
        if challenge and challenge.expires_at > now:
            if challenge.attempts >= MAX_ATTEMPTS:
                return "locked"
            if challenge.sent_at + RESEND_INTERVAL > now:
                return "cooldown"
        EmailOTPChallenge.objects.update_or_create(
            user=user,
            defaults={
                "code_hash": code_digest(user.pk, token, code),
                "expires_at": now + OTP_LIFETIME,
                "sent_at": now,
                "attempts": challenge.attempts if challenge and challenge.expires_at > now else 0,
            },
        )

    try:
        sent = send_mail(
            "Tu código de acceso a Rock del País",
            f"Tu código de verificación es {code}. Vence en 10 minutos. No lo compartas.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        if sent != 1:
            logger.error("Verification email was not accepted for delivery")
            return "email_error"
    except (smtplib.SMTPException, OSError):
        logger.exception("Could not send verification email")
        return "email_error"
    return "sent"
