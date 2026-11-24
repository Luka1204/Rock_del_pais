import json
import re
from io import StringIO
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import (
    Category,
    Consultation,
    EmailOTPChallenge,
    Order,
    OrderItem,
    Product,
    SavedCart,
)
from .otp import MAX_ATTEMPTS


class ProductSeederTests(TestCase):
    def test_seed_creates_catalog_and_is_idempotent(self):
        output = StringIO()
        call_command("sembrar_productos", stdout=output)
        initial_count = Product.objects.count()
        self.assertGreater(initial_count, 0)
        self.assertIn(f"Productos creados: {initial_count}", output.getvalue())
        self.assertEqual(
            set(Product.objects.values_list("category__slug", flat=True)),
            {"discos", "instrumentos", "amplificadores", "accesorios"},
        )
        self.assertTrue(Product.objects.filter(brand="Charly García", stock__gt=0).exists())
        self.assertEqual(
            Product.objects.filter(active=True, category__active=True).count(), initial_count
        )

        product = Product.objects.get(slug="vinilo-artaud-pescado-rabioso")
        product.stock = 0
        product.price = "999.00"
        product.save()
        category = product.category
        category.active = False
        category.save()

        output = StringIO()
        call_command("sembrar_productos", stdout=output)
        self.assertIn("Productos creados: 0", output.getvalue())
        self.assertIn("categorías están inactivas", output.getvalue())
        self.assertEqual(Product.objects.count(), initial_count)
        product.refresh_from_db()
        category.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(str(product.price), "999.00")
        self.assertFalse(category.active)

    def test_seed_preserves_existing_product_with_same_slug(self):
        category = Category.objects.create(name="Otra categoría")
        product = Product.objects.create(
            slug="vinilo-artaud-pescado-rabioso",
            name="Producto existente",
            category=category,
            price="100.00",
            stock=7,
        )
        output = StringIO()
        call_command("sembrar_productos", stdout=output)
        product.refresh_from_db()
        self.assertEqual(product.name, "Producto existente")
        self.assertEqual(product.category, category)
        self.assertEqual(product.stock, 7)
        self.assertIn("Ya existentes, sin modificar: 1", output.getvalue())


@override_settings(ALLOWED_HOSTS=["testserver"])
class AssignmentDemonstrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usuario", password="una-clave-segura-123"
        )

    def login_verified(self, client):
        client.force_login(self.user)
        session = client.session
        session["otp_verified"] = True
        session.save()

    def test_jwt_requires_verified_login_and_contains_only_demo_claims(self):
        url = reverse("cuenta_sesion")
        self.assertRedirects(
            self.client.post(url), f"{reverse('login')}?next={url}",
            fetch_redirect_response=False,
        )
        self.login_verified(self.client)
        session_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, session_key)
        self.assertIn("no-store", response["Cache-Control"])
        key = salted_hmac("store.demo_jwt", settings.SECRET_KEY, algorithm="sha256").hexdigest()
        claims = jwt.decode(response.context["token"], key, algorithms=["HS256"])
        self.assertEqual(claims["sub"], str(self.user.pk))
        self.assertEqual(claims["purpose"], "demostracion")
        self.assertEqual(claims["exp"] - claims["iat"], 300)
        self.assertEqual(set(claims), {"sub", "iat", "exp", "purpose"})

    def test_jwt_generation_requires_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.login_verified(client)
        url = reverse("cuenta_sesion")
        response = client.get(url)
        self.assertIsNone(response.context["token"])
        self.assertEqual(client.post(url).status_code, 403)
        csrf = response.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": csrf}).status_code, 200)

    def test_product_api_page_and_graphql_query(self):
        category = Category.objects.create(name="Discos")
        Product.objects.create(name="Publicado", category=category, price="100", stock=2)
        Product.objects.create(name="Oculto", category=category, price="100", active=False)
        response = self.client.get(reverse("productos_api"))
        self.assertContains(response, reverse("graphql"))
        self.assertContains(response, "productos_api.js")
        response = self.client.get(reverse("graphql"), {
            "query": "{ products { name price stock category { name } } }",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["products"],
            [{"name": "Publicado", "price": "100.00", "stock": 2, "category": {"name": "Discos"}}],
        )


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

    def test_cart_is_restored_for_same_user_after_logout_and_cleared_at_checkout(self):
        category = Category.objects.create(name="Discos")
        product = Product.objects.create(
            name="Disco", category=category, price="100.00", stock=3
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["otp_verified"] = True
        session.save()
        self.client.post(
            reverse("agregar_al_carrito", args=[product.pk]),
            {"quantity": 3},
        )
        self.assertEqual(
            SavedCart.objects.get(user=self.user).items,
            {str(product.pk): 3},
        )

        self.client.post(reverse("logout"))
        self.assertEqual(self.client.session.get("cart", {}), {})
        self.assertNotIn("_auth_user_id", self.client.session)

        self.start_login()
        response = self.client.post(
            reverse("verify_email_code"),
            {"code": self.sent_code()},
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.session["cart"], {str(product.pk): 3})

        response = self.client.post(
            reverse("checkout"),
            {
                "full_name": "Cliente",
                "email": self.user.email,
                "phone": "123",
                "address": "Retiro",
                "delivery_notes": "",
                "payment_method": Order.PaymentMethod.CASH,
            },
        )
        self.assertRedirects(
            response,
            reverse("checkout_confirmacion"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session.get("cart", {}), {})
        self.assertFalse(SavedCart.objects.filter(user=self.user).exists())

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

    def graphql(self, query, variables=None):
        response = self.client.post(
            reverse("graphql"),
            data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_graphql_catalog_hides_unpublished_products(self):
        Product.objects.create(
            name="Oculto", description="No publicar", category=self.category,
            price="10.00", active=False,
        )
        response = self.graphql(
            "{ products(search: \"disco\") { name category { name } } }"
        )

        self.assertNotIn("errors", response)
        self.assertEqual(
            response["data"]["products"],
            [{"name": "Disco", "category": {"name": "Discos"}}],
        )

    def test_graphql_cart_mutations_validate_stock(self):
        response = self.graphql(
            "mutation { addToCart(productId: %d, quantity: 2) "
            "{ cart { total itemCount items { quantity } } } }" % self.product.pk
        )
        self.assertNotIn("errors", response)
        self.assertEqual(
            self.client.session["cart"], {str(self.product.pk): 2}
        )

        response = self.graphql(
            "mutation { addToCart(productId: %d, quantity: 2) "
            "{ cart { total } } }" % self.product.pk
        )
        self.assertIn("errors", response)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 2})

        response = self.graphql(
            "mutation { updateCart(productId: %d, quantity: 3) "
            "{ cart { itemCount } } }" % self.product.pk
        )
        self.assertNotIn("errors", response)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 3})

        response = self.graphql(
            "mutation { removeFromCart(productId: %d) "
            "{ cart { itemCount } } }" % self.product.pk
        )
        self.assertNotIn("errors", response)
        self.assertEqual(self.client.session["cart"], {})

    def test_graphql_checkout_creates_order_and_decrements_stock(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.graphql(
            "mutation { createOrder(fullName: \"Cliente\", "
            "email: \"cliente@example.com\", phone: \"123\", address: \"Retiro\", "
            "paymentMethod: \"efectivo\") { order { id total status } } }"
        )

        self.assertNotIn("errors", response)
        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("2500.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.client.session["cart"], {})

    def test_graphql_checkout_rejects_insufficient_stock_without_partial_order(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 4}
        session.save()

        response = self.graphql(
            "mutation { createOrder(fullName: \"Cliente\", "
            "email: \"cliente@example.com\", phone: \"123\", address: \"Retiro\", "
            "paymentMethod: \"efectivo\") { order { id } } }"
        )

        self.assertIn("errors", response)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 4})

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

    def test_checkout_creates_pending_order_and_reserves_stock(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.post(reverse("checkout"), {
            "full_name": "Cliente de prueba",
            "email": "cliente@example.com",
            "phone": "1122334455",
            "address": "Calle 123",
            "delivery_notes": "",
            "payment_method": Order.PaymentMethod.CASH,
        })

        order = Order.objects.get()
        item = order.items.get()
        self.assertRedirects(
            response, reverse("checkout_confirmacion"), fetch_redirect_response=False
        )
        self.assertEqual(order.total, Decimal(self.product.price) * 2)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.client.session["cart"], {})
        self.assertContains(self.client.get(reverse("checkout_confirmacion")), "No se realizó ningún cobro")

    def test_checkout_rejects_cart_quantity_over_current_stock(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 4}
        session.save()

        response = self.client.post(reverse("checkout"), {
            "full_name": "Cliente de prueba",
            "email": "cliente@example.com",
            "phone": "1122334455",
            "address": "Calle 123",
            "delivery_notes": "",
            "payment_method": Order.PaymentMethod.CASH,
        })

        self.assertRedirects(response, reverse("carrito"))
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 3})

    def test_management_requires_administrator_for_every_route(self):
        routes = [
            ("management_home", []), ("management_product_list", []),
            ("management_category_list", []), ("category_create", []),
            ("category_edit", [self.category.pk]), ("category_delete", [self.category.pk]),
            ("management_order_list", []), ("management_order_edit", [1]),
            ("management_user_list", []), ("management_user_create", []),
            ("management_user_edit", [1]), ("management_user_delete", [1]),
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

    def test_staff_can_manage_order_status_and_reserved_stock(self):
        order = Order.objects.create(
            full_name="Cliente prueba", email="cliente@example.com", phone="123",
            address="Retiro", payment_method=Order.PaymentMethod.CASH, total="2500.00",
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            unit_price=self.product.price, quantity=2,
        )
        self.product.stock = 1
        self.product.save()
        self.login_staff()

        edit_url = reverse("management_order_edit", args=[order.pk])
        self.assertContains(self.client.get(edit_url), "En despacho")
        order_data = {
            "full_name": order.full_name,
            "email": order.email,
            "phone": order.phone,
            "address": order.address,
            "delivery_notes": "",
            "payment_method": Order.PaymentMethod.CASH,
            "status": Order.Status.CANCELLED,
        }
        response = self.client.post(edit_url, order_data)
        self.assertRedirects(response, reverse("management_order_list"))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(order.stock_reserved)
        self.assertEqual(self.product.stock, 3)

        order_data["status"] = Order.Status.IN_TRANSIT
        response = self.client.post(edit_url, order_data)
        self.assertRedirects(response, reverse("management_order_list"))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_TRANSIT)
        self.assertTrue(order.stock_reserved)
        self.assertEqual(self.product.stock, 1)

        order_data["status"] = Order.Status.CANCELLED
        self.client.post(edit_url, order_data)
        self.product.stock = 0
        self.product.save()
        order_data["status"] = Order.Status.IN_TRANSIT
        response = self.client.post(edit_url, order_data)
        self.assertContains(response, "No hay stock suficiente")
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(order.stock_reserved)
        self.assertEqual(self.product.stock, 0)

    def test_staff_can_create_edit_and_delete_users_with_roles(self):
        self.login_staff()
        create_url = reverse("management_user_create")
        self.assertContains(
            self.client.post(create_url, {}),
            "Este campo es obligatorio",
        )
        response = self.client.post(create_url, {
            "username": "nuevo",
            "email": "nuevo@example.com",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "role": "administrador",
            "password1": "Una-clave-segura-123!",
            "password2": "Una-clave-segura-123!",
        })
        self.assertRedirects(response, reverse("management_user_list"))
        account = get_user_model().objects.get(username="nuevo")
        self.assertTrue(account.is_staff)

        edit_url = reverse("management_user_edit", args=[account.pk])
        response = self.client.post(edit_url, {
            "username": "nuevo",
            "email": "nuevo@example.com",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "role": "cliente",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("management_user_list"))
        account.refresh_from_db()
        self.assertFalse(account.is_staff)

        delete_url = reverse("management_user_delete", args=[account.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("management_user_list"))
        self.assertFalse(get_user_model().objects.filter(pk=account.pk).exists())

    def test_staff_cannot_remove_their_own_admin_role_or_delete_themselves(self):
        self.login_staff()
        edit_url = reverse("management_user_edit", args=[self.staff.pk])
        response = self.client.post(edit_url, {
            "username": self.staff.username,
            "email": "",
            "first_name": "",
            "last_name": "",
            "role": "cliente",
            "is_active": "",
        })
        self.assertRedirects(response, reverse("management_user_list"))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)
        self.assertTrue(self.staff.is_active)

        response = self.client.post(
            reverse("management_user_delete", args=[self.staff.pk]), follow=True
        )
        self.assertContains(response, "No podés eliminar tu propio usuario")
        self.assertTrue(get_user_model().objects.filter(pk=self.staff.pk).exists())


class ConsultationTests(TestCase):
    def test_valid_contact_submission_is_persisted(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Visitante de prueba",
                "email": "visitante@example.com",
                "subject": "Consulta de prueba",
                "message": "Quisiera recibir más información.",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("contact"))
        self.assertTrue(
            Consultation.objects.filter(
                name="Visitante de prueba",
                email="visitante@example.com",
                subject="Consulta de prueba",
                message="Quisiera recibir más información.",
            ).exists()
        )
        self.assertContains(response, "Consulta enviada con éxito")

    def test_invalid_contact_submission_is_not_persisted(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "",
                "email": "correo-invalido",
                "subject": "Consulta de prueba",
                "message": "Mensaje",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Consultation.objects.count(), 0)
