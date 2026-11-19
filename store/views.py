from django.shortcuts import render
import csv
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import (
    CartAddForm,
    CheckoutForm,
    ConsultationForm,
    ManagedCategoryForm,
    ManagedOrderForm,
    ManagedOrderItemFormSet,
    ManagedProductForm,
    ManagedUserChangeForm,
    ManagedUserCreationForm,
    RegistrationForm,
)
from .models import Category, Consultation, Order, OrderItem, Product
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

def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "¡Bienvenido! Tu cuenta ha sido creada.")
        return redirect("home")
    return render(
        request,
        "store/registro_form.html",
        {"form": form, "title": "Registro"},
    )

def logout_view(request):
    logout(request)
    messages.success(request, "Has cerrado sesión correctamente.")
    return redirect("home")
# Create your views here.
