from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, AuthenticationForm
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import Category, Consultation, Order, OrderItem, Product

User = get_user_model()


class EmailOTPForm(forms.Form):
    code = forms.RegexField(
        regex=r"^[0-9]{6}$",
        label="Código de verificación",
        error_messages={"invalid": "Ingresá el código de 6 dígitos."},
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "maxlength": "6"}
        ),
    )


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico")
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellido", max_length=150)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Nombre de usuario"}


class ManagedUserCreationForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico", required=False)
    first_name = forms.CharField(label="Nombre", max_length=150, required=False)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Nombre de usuario"}


class ManagedUserChangeForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")
        labels = {
            "username": "Nombre de usuario",
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "is_active": "Cuenta activa",
        }


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ("name", "email", "subject", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}


class CartAddForm(forms.Form):
    quantity = forms.IntegerField(
        label="Cantidad", min_value=1, max_value=99, initial=1,
        widget=forms.NumberInput(attrs={"min": 1, "max": 99}),
    )


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            "full_name",
            "email",
            "phone",
            "address",
            "delivery_notes",
            "payment_method",
        )
        widgets = {
            "delivery_notes": forms.TextInput(attrs={"placeholder": "Opcional"}),
        }


class ManagedCategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "slug", "active", "sort_order")
        labels = {
            "name": "Nombre",
            "slug": "Identificador URL",
            "active": "Categoría activa",
            "sort_order": "Orden de aparición",
        }


class ManagedProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name",
            "brand",
            "slug",
            "description",
            "category",
            "price",
            "stock",
            "image_url",
            "image_credit",
            "image_source_url",
            "active",
        )
        labels = {
            "name": "Nombre",
            "brand": "Marca",
            "slug": "Identificador URL",
            "description": "Descripción",
            "category": "Categoría",
            "price": "Precio",
            "stock": "Unidades disponibles",
            "image_url": "URL de la imagen",
            "image_credit": "Crédito de la imagen",
            "image_source_url": "Enlace a la fuente de la imagen",
            "active": "Producto publicado",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = Category.objects.filter(active=True)
        if self.instance.pk:
            categories = Category.objects.filter(
                Q(active=True) | Q(pk=self.instance.category_id)
            )
        self.fields["category"].queryset = categories


class ManagedOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            "full_name",
            "email",
            "phone",
            "address",
            "delivery_notes",
            "payment_method",
            "status",
        )
        labels = {
            "full_name": "Nombre y apellido",
            "email": "Correo electrónico",
            "phone": "Teléfono",
            "address": "Domicilio o punto de retiro",
            "delivery_notes": "Indicaciones",
            "payment_method": "Medio de pago",
            "status": "Estado del pedido",
        }


class ManagedOrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ("product", "quantity")
        labels = {"product": "Producto", "quantity": "Cantidad"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            active=True, category__active=True
        ).select_related("category")
        self.fields["product"].label_from_instance = (
            lambda product: f"{product.name} · {product.stock} disponibles"
        )


ManagedOrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=ManagedOrderItemForm,
    fields=("product", "quantity"),
    extra=1,
    can_delete=False,
    min_num=1,
    validate_min=True,
)
