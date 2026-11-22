from django.db import migrations, models
from django.utils.text import slugify


def migrate_products(apps, schema_editor):
    Producto = apps.get_model("store", "Producto")
    Product = apps.get_model("store", "Product")
    Category = apps.get_model("store", "Category")
    db = schema_editor.connection.alias
    old_products = Producto.objects.using(db).order_by("pk")
    if not old_products.exists():
        return

    base_slug = "sin-categoria"
    category_slug = base_slug
    suffix = 2
    while Category.objects.using(db).filter(slug=category_slug).exists():
        suffix_text = f"-{suffix}"
        category_slug = f"{base_slug[:20 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    category = Category.objects.using(db).create(name="Sin categoría", slug=category_slug)

    for old in old_products.iterator():
        base_slug = slugify(old.nombre)[:120] or "producto"
        slug = base_slug
        suffix = 2
        while Product.objects.using(db).filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        product = Product.objects.using(db).create(
            name=old.nombre,
            slug=slug,
            description=old.descripcion,
            category=category,
            price=old.precio,
            stock=old.stock,
            active=old.disponible,
        )
        Product.objects.using(db).filter(pk=product.pk).update(created_at=old.creado_en)


class Migration(migrations.Migration):
    dependencies = [("store", "0003_producto")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="name",
            field=models.CharField(max_length=150, verbose_name="nombre"),
        ),
        migrations.AlterField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, verbose_name="descripción"),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="product_name",
            field=models.CharField(max_length=150, verbose_name="producto"),
        ),
        migrations.RunPython(migrate_products),
        migrations.DeleteModel(name="Producto"),
    ]
