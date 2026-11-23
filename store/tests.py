import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Consultation, EmailOTPChallenge, Order, OrderItem, Product
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

    def test_login_form_preserves_safe_next(self):
        response = self.client.get(reverse("login"), {"next": "/admin/"})
        self.assertContains(response, 'name="next" value="/admin/"')
        response = self.client.get(reverse("login"), {"next": "https://evil.example/"})
        self.assertNotContains(response, 'name="next"')

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


@override_settings(ALLOWED_HOSTS=["testserver"])
class ProductCatalogTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Discos")
        self.product = Product.objects.create(
            name="Disco", description="Edición original", category=self.category,
            price="1250.00", stock=3,
        )
        self.staff = get_user_model().objects.create_user(
            username="admin", password="clave-segura-123", is_staff=True
        )

    def login_staff(self):
        self.client.force_login(self.staff)
        session = self.client.session
        session["otp_verified"] = True
        session.save()

    def test_public_catalog_and_home_show_published_products_only(self):
        inactive = Product.objects.create(
            name="Oculto", description="Oculto", category=self.category,
            price="10.00", active=False,
        )
        inactive_category = Category.objects.create(name="Pausada", active=False)
        hidden_by_category = Product.objects.create(
            name="Categoría pausada", description="Oculto", category=inactive_category,
            price="10.00",
        )
        for url in ("home", "producto_lista"):
            response = self.client.get(reverse(url))
            self.assertContains(response, "Disco")
            self.assertNotContains(response, "Oculto")
            self.assertNotContains(response, "Categoría pausada")
        self.assertContains(self.client.get(reverse("producto_detalle", args=[self.product.pk])), "Edición original")
        for product in (inactive, hidden_by_category):
            self.assertEqual(self.client.get(reverse("producto_detalle", args=[product.pk])).status_code, 404)

    def test_staff_creates_edits_and_deletes_product(self):
        self.login_staff()
        data = {
            "name": "Guitarra", "brand": "Marca", "description": "Eléctrica",
            "category": self.category.pk, "price": "12000.00", "stock": 2,
            "image_url": "https://example.com/guitarra.jpg", "active": "on",
        }
        response = self.client.post(reverse("producto_crear"), data)
        self.assertRedirects(response, reverse("producto_lista"))
        product = Product.objects.get(name="Guitarra")
        self.assertEqual(product.brand, "Marca")
        self.assertContains(self.client.get(reverse("producto_detalle", args=[product.pk])), "guitarra.jpg")
        data["name"] = "Guitarra editada"
        data["description"] = ""
        data.pop("active")
        response = self.client.post(reverse("producto_editar", args=[product.pk]), data)
        self.assertRedirects(response, reverse("producto_lista"))
        product.refresh_from_db()
        self.assertEqual(product.name, "Guitarra editada")
        self.assertEqual(product.description, "")
        self.assertFalse(product.active)
        self.assertContains(self.client.get(reverse("producto_lista")), "Guitarra editada")
        self.assertRedirects(
            self.client.post(reverse("producto_eliminar", args=[product.pk])), reverse("producto_lista")
        )
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_form_displays_errors_and_non_staff_cannot_modify(self):
        self.login_staff()
        response = self.client.post(reverse("producto_crear"), {"name": "Sin categoría"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo es obligatorio")
        self.assertFalse(Product.objects.filter(name="Sin categoría").exists())
        self.staff.is_staff = False
        self.staff.save()
        self.assertEqual(self.client.post(reverse("producto_eliminar", args=[self.product.pk])).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_catalog_combines_search_category_stock_and_ordering(self):
        other_category = Category.objects.create(name="Instrumentos")
        Product.objects.create(
            name="Guitarra", brand="Disco", description="Instrumento", category=other_category,
            price="500.00", stock=5,
        )
        Product.objects.create(
            name="Vinilo", brand="Disco", description="Colección", category=self.category,
            price="300.00", stock=0,
        )
        second = Product.objects.create(
            name="Otro disco", description="Edición original", category=self.category,
            price="2000.00", stock=2,
        )
        response = self.client.get(reverse("producto_lista"), {
            "q": "edición", "category": self.category.slug, "stock": "available", "sort": "price_desc",
        })
        self.assertEqual(list(response.context["productos"]), [second, self.product])
        response = self.client.get(reverse("producto_lista"), {"q": "disco", "stock": "unavailable"})
        self.assertEqual([p.name for p in response.context["productos"]], ["Vinilo"])
        response = self.client.get(reverse("producto_lista"), {"category": "inexistente"})
        self.assertFalse(response.context["filter_form"].is_valid())
        self.assertContains(response, response.context["filter_form"].errors["category"][0])
        self.assertEqual(list(response.context["productos"]), [])

    def test_cart_quantity_controls_and_product_thumbnail(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.get(reverse("carrito"))
        self.assertContains(response, "cart-item-image")
        self.assertContains(response, "RDP")

        self.client.post(reverse("agregar_al_carrito", args=[self.product.pk]))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 3})
        self.client.post(reverse("agregar_al_carrito", args=[self.product.pk]))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 3})

        response = self.client.post(reverse("quitar_del_carrito", args=[self.product.pk]))
        self.assertRedirects(response, reverse("carrito"))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 2})

        self.client.post(reverse("quitar_del_carrito", args=[self.product.pk]))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})

        self.client.post(reverse("quitar_del_carrito", args=[self.product.pk]))
        self.assertEqual(self.client.session["cart"], {})

    def test_removing_item_from_cart_keeps_other_items(self):
        other_product = Product.objects.create(
            name="Otro disco", description="Edición especial", category=self.category,
            price="1500.00", stock=4,
        )
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2, str(other_product.pk): 1}
        session.save()

        response = self.client.post(reverse("eliminar_del_carrito", args=[self.product.pk]))

        self.assertRedirects(response, reverse("carrito"))
        self.assertEqual(self.client.session["cart"], {str(other_product.pk): 1})

    def test_management_requires_administrator_for_every_route(self):
        routes = [
            ("management_home", []), ("management_product_list", []),
            ("management_category_list", []), ("category_create", []),
            ("category_edit", [self.category.pk]), ("category_delete", [self.category.pk]),
            ("management_order_list", []), ("management_user_list", []),
            ("management_consultation_list", []),
        ]
        for name, args in routes:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302)
        self.login_staff()
        self.staff.is_staff = False
        self.staff.save()
        for name, args in routes:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name, args=args)).status_code, 403)
        self.assertNotContains(self.client.get(reverse("home")), "Panel de gestión")

    def test_management_shows_real_data_and_category_actions_work(self):
        order = Order.objects.create(
            full_name="Cliente prueba", email="cliente@example.com", phone="123",
            address="Retiro", payment_method=Order.PaymentMethod.CASH, total="1250.00",
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            unit_price=self.product.price, quantity=1,
        )
        Consultation.objects.create(
            name="Visitante", email="visitante@example.com", subject="Consulta especial", message="Hola"
        )
        self.login_staff()
        for name, text in (
            ("management_home", "Productos"), ("management_product_list", "Disco"),
            ("management_category_list", "Discos"), ("management_order_list", "Cliente prueba"),
            ("management_user_list", "admin"), ("management_consultation_list", "Consulta especial"),
        ):
            self.assertContains(self.client.get(reverse(name)), text)
        self.assertContains(self.client.post(reverse("category_create"), {}), "Este campo es obligatorio")
        response = self.client.post(reverse("category_create"), {
            "name": "Accesorios", "active": "on", "sort_order": 0,
        })
        self.assertRedirects(response, reverse("management_category_list"))
        self.assertTrue(Category.objects.filter(name="Accesorios").exists())
        response = self.client.get(reverse("category_edit", args=[self.category.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("category_edit", args=[self.category.pk]), {
            "name": "Discos editados", "slug": self.category.slug, "active": "on", "sort_order": 0,
        })
        self.assertRedirects(response, reverse("management_category_list"))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Discos editados")
        self.assertEqual(self.client.get(reverse("category_delete", args=[self.category.pk])).status_code, 200)
        response = self.client.post(reverse("category_delete", args=[self.category.pk]), follow=True)
        self.assertContains(response, "No se puede eliminar una categoría con productos")
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
