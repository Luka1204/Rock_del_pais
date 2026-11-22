from django.shortcuts import render
import csv
import secrets
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import (
    CartAddForm,
    CheckoutForm,
    ConsultationForm,
    EmailOTPForm,
    ManagedCategoryForm,
    ManagedOrderForm,
    ManagedOrderItemFormSet,
    ManagedProductForm,
    ManagedUserChangeForm,
    ManagedUserCreationForm,
    RegistrationForm,
)
from .models import Category, Consultation, EmailOTPChallenge, Order, OrderItem, Product
from .otp import MAX_ATTEMPTS, code_digest, issue_code, valid_email

from .forms import ProductoForm
from .models import Producto


from django.core.exceptions import PermissionDenied



def home(request):
    return render(request, "store/home.html")

def management_category_list(request):
    categories = Category.objects.annotate(product_count=Count("products"))
    return render(
        request,
        "store/management_category_list.html",
        {"categories": categories},
    )

def category_create(request):
    form = ManagedCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Creamos la categoría.")
        return redirect("management_category_list")
    return render(
        request,
        "store/management_category_form.html",
        {"form": form, "title": "Nueva categoría"},
    )


def category_edit(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    form = ManagedCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guardamos los cambios de la categoría.")
        return redirect("management_category_list")
    return render(
        request,
        "store/management_category_form.html",
        {"form": form, "title": "Editar categoría", "category": category},
    )


def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "POST":
        try:
            category.delete()
        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar una categoría con productos. Reasignalos primero.",
            )
            return redirect("management_category_list")
        messages.success(request, "Eliminamos la categoría.")
        return redirect("management_category_list")
    return render(
        request,
        "store/management_category_confirm_delete.html",
        {"category": category},
    )

def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return ""


def _issue_error(request, result):
    errors = {
        "missing_email": "Tu cuenta no tiene un correo válido. Contactá a un administrador.",
        "email_error": "No pudimos enviar el código. Contactá al administrador o intentá más tarde.",
        "cooldown": "Esperá un minuto antes de solicitar otro código.",
        "locked": "Agotaste los intentos. Esperá a que venza el código antes de intentarlo de nuevo.",
    }
    messages.error(request, errors[result])


def _start_verification(request, user, backend, next_url=""):
    if request.user.is_authenticated:
        logout(request)
    else:
        request.session.cycle_key()
    request.session.pop("pending_otp", None)
    token = secrets.token_urlsafe(32)
    result = issue_code(user, token)
    if result != "sent":
        _issue_error(request, result)
        return False
    request.session["pending_otp"] = {
        "user_id": user.pk,
        "backend": backend,
        "token": token,
        "auth_hash": user.get_session_auth_hash(),
        "email": user.email,
        "next": next_url,
    }
    return True


def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if _start_verification(request, user, settings.AUTHENTICATION_BACKENDS[0]):
            messages.success(request, "Creamos tu cuenta. Verificá tu correo para ingresar.")
            return redirect("verify_email_code")
        messages.warning(request, "Tu cuenta fue creada. Intentá iniciar sesión cuando se solucione el envío.")
        return redirect("login")
    return render(
        request,
        "store/registro_form.html",
        {"form": form, "title": "Registro"},
    )

def login_view(request):
    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next", ""))
    form = AuthenticationForm(request, data=request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if _start_verification(request, user, user.backend, next_url):
            return redirect("verify_email_code")
    return render(
        request,
        "store/login.html",
        {"form": form, "title": "Iniciar sesión", "next": next_url},
    )


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin:index")
    from django.contrib.auth.views import redirect_to_login

    next_url = _safe_next(request, request.GET.get("next", "")) or "/admin/"
    return redirect_to_login(next_url, "login")


def _pending_user(request):
    pending = request.session.get("pending_otp")
    if not isinstance(pending, dict):
        return None, None
    user = get_user_model().objects.filter(pk=pending.get("user_id"), is_active=True).first()
    if (
        not user
        or not valid_email(user)
        or user.email != pending.get("email")
        or not constant_time_compare(user.get_session_auth_hash(), pending.get("auth_hash", ""))
        or pending.get("backend") not in settings.AUTHENTICATION_BACKENDS
        or not isinstance(pending.get("token"), str)
    ):
        request.session.pop("pending_otp", None)
        return None, None
    return user, pending


def verify_email_code(request):
    user, pending = _pending_user(request)
    if not user:
        messages.error(request, "Iniciá sesión para solicitar un código de verificación.")
        return redirect("login")
    form = EmailOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = "invalid"
        with transaction.atomic():
            challenge = EmailOTPChallenge.objects.select_for_update().filter(user=user).first()
            if not challenge or challenge.expires_at <= timezone.now():
                result = "expired"
            elif challenge.attempts >= MAX_ATTEMPTS:
                result = "locked"
            elif constant_time_compare(
                challenge.code_hash, code_digest(user.pk, pending["token"], form.cleaned_data["code"])
            ):
                challenge.delete()
                result = "verified"
            else:
                challenge.attempts += 1
                challenge.save(update_fields=["attempts"])
                if challenge.attempts >= MAX_ATTEMPTS:
                    result = "locked"
        if result == "verified":
            next_url = _safe_next(request, pending.get("next", ""))
            login(request, user, backend=pending["backend"])
            request.session.pop("pending_otp", None)
            request.session["otp_verified"] = True
            messages.success(request, "Tu identidad fue verificada. ¡Bienvenido!")
            return redirect(next_url or "home")
        if result == "locked":
            _issue_error(request, "locked")
        elif result == "expired":
            messages.error(request, "El código venció o ya fue utilizado. Solicitá uno nuevo.")
        else:
            form.add_error("code", "El código es incorrecto.")
    return render(request, "store/verify_email_code.html", {"form": form})


@require_POST
def resend_email_code(request):
    user, pending = _pending_user(request)
    if not user:    
        messages.error(request, "Iniciá sesión para solicitar un código de verificación.")
        return redirect("login")
    result = issue_code(user, pending["token"])
    if result == "sent":
        messages.success(request, "Te enviamos un nuevo código.")
    else:
        _issue_error(request, result)
    return redirect("verify_email_code")


def logout_view(request):
    logout(request)
    messages.success(request, "Has cerrado sesión correctamente.")
    return redirect("home")
# Create your views here.




def producto_lista(request):
    productos = Producto.objects.all()
    return render(request, "store/producto_lista.html", {"productos": productos})


def producto_detalle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return render(request, "store/producto_detalle.html", {"producto": producto})


@login_required
def producto_crear(request):
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("producto_lista")
    else:
        form = ProductoForm()
    return render(
        request,
        "store/producto_form.html",
        {"form": form, "titulo": "Crear producto"},
    )


@login_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect("producto_lista")
    else:
        form = ProductoForm(instance=producto)
    return render(
        request,
        "store/producto_form.html",
        {"form": form, "titulo": "Editar producto"},
    )


@login_required
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        producto.delete()
        return redirect("producto_lista")
    return render(
        request,
        "store/producto_confirmar_eliminar.html",
        {"producto": producto},
    )



def admin_requerido(view_func):
    
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("No tenés permisos de administrador.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view



def producto_lista(request):
    productos = Producto.objects.all()
    return render(request, "store/producto_lista.html", {"productos": productos})


def producto_detalle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return render(request, "store/producto_detalle.html", {"producto": producto})


@admin_requerido
def producto_crear(request):
    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto creado correctamente.")
            return redirect("producto_lista")
    else:
        form = ProductoForm()
    return render(request, "store/producto_form.html", {"form": form, "accion": "Crear"})


@admin_requerido
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("producto_lista")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "store/producto_form.html", {"form": form, "accion": "Editar"})


@admin_requerido
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        producto.delete()
        messages.success(request, "Producto eliminado correctamente.")
        return redirect("producto_lista")
    return render(request, "store/producto_confirmar_eliminar.html", {"producto": producto})