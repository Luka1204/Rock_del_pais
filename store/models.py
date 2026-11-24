from django.conf import settings
from django.db import models
from django.utils.text import slugify


class EmailOTPChallenge(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)


class Category(models.Model):
    name = models.CharField("nombre", max_length=80)
    slug = models.SlugField("identificador", max_length=20, unique=True, blank=True)
    active = models.BooleanField("activa", default=True)
    sort_order = models.PositiveIntegerField("orden", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:20] or "categoria"
            candidate = base_slug
            suffix = 2
            while Category.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                suffix_text = f"-{suffix}"
                candidate = f"{base_slug[:20 - len(suffix_text)]}{suffix_text}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):

    name = models.CharField("nombre", max_length=150)
    brand = models.CharField("marca", max_length=100, blank=True)
    slug = models.SlugField(unique=True, max_length=140, blank=True)
    description = models.TextField("descripción", blank=True)
    category = models.ForeignKey(
        Category,
        verbose_name="categoría",
        on_delete=models.PROTECT,
        related_name="products",
    )
    price = models.DecimalField("precio", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField("stock", default=0)
    image_url = models.URLField("URL de imagen", max_length=500, blank=True)
    image_credit = models.CharField("crédito de imagen", max_length=160, blank=True)
    image_source_url = models.URLField("fuente de imagen", max_length=500, blank=True)
    active = models.BooleanField("publicado", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:120] or "producto"
            candidate = base_slug
            suffix = 2
            while Product.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SavedCart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_cart",
    )
    items = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        TRANSFER = "transferencia", "Transferencia bancaria"
        CASH = "efectivo", "Efectivo al retirar"

    class Status(models.TextChoices):
        PENDING = "pendiente", "Pendiente"
        CONFIRMED = "confirmado", "Confirmado"
        DISPATCH = "en_despacho", "En despacho"
        IN_TRANSIT = "en_camino", "En camino"
        COMPLETED = "completado", "Finalizado"
        CANCELLED = "cancelado", "Cancelado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    full_name = models.CharField("nombre y apellido", max_length=140)
    email = models.EmailField("correo electrónico")
    phone = models.CharField("teléfono", max_length=30)
    address = models.CharField("domicilio o punto de retiro", max_length=240)
    delivery_notes = models.CharField("indicaciones", max_length=240, blank=True)
    payment_method = models.CharField(
        "medio de pago", max_length=20, choices=PaymentMethod.choices
    )
    status = models.CharField("estado", max_length=20, choices=Status.choices, default=Status.PENDING)
    total = models.DecimalField("total", max_digits=10, decimal_places=2)
    stock_reserved = models.BooleanField(
        "stock reservado", default=True, help_text="Indica si el stock de los artículos sigue reservado."
    )
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} - {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items"
    )
    product_name = models.CharField("producto", max_length=150)
    unit_price = models.DecimalField("precio unitario", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("cantidad")

    class Meta:
        verbose_name = "artículo de pedido"
        verbose_name_plural = "artículos de pedido"

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class Consultation(models.Model):
    name = models.CharField("nombre", max_length=120)
    email = models.EmailField("correo electrónico")
    subject = models.CharField("asunto", max_length=160)
    message = models.TextField("mensaje")
    created_at = models.DateTimeField("recibida", auto_now_add=True)
    answered = models.BooleanField("respondida", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "consulta"
        verbose_name_plural = "consultas"

    def __str__(self):
        return f"{self.subject} - {self.name}"