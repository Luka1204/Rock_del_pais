from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import Category, Product


CATEGORIES = (
    ("discos", "Discos", 1),
    ("instrumentos", "Instrumentos", 2),
    ("amplificadores", "Amplificadores", 3),
    ("accesorios", "Accesorios", 4),
)

PRODUCTS = (
    {
        "slug": "vinilo-artaud-pescado-rabioso",
        "name": "Artaud - Vinilo",
        "brand": "Pescado Rabioso",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "45000.00",
        "stock": 5,
    },
    {
        "slug": "vinilo-clics-modernos-charly-garcia",
        "name": "Clics modernos - Vinilo",
        "brand": "Charly García",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "42000.00",
        "stock": 6,
    },
    {
        "slug": "vinilo-cancion-animal-soda-stereo",
        "name": "Canción animal - Vinilo",
        "brand": "Soda Stereo",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "44000.00",
        "stock": 4,
    },
    {
        "slug": "vinilo-oktubre-patricio-rey",
        "name": "Oktubre - Vinilo",
        "brand": "Patricio Rey y sus Redonditos de Ricota",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "47000.00",
        "stock": 3,
    },
    {
        "slug": "vinilo-el-amor-despues-del-amor-fito-paez",
        "name": "El amor después del amor - Vinilo",
        "brand": "Fito Páez",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "43000.00",
        "stock": 5,
    },
    {
        "slug": "vinilo-almendra-almendra",
        "name": "Almendra - Vinilo",
        "brand": "Almendra",
        "description": "Álbum de rock argentino en formato vinilo.",
        "category": "discos",
        "price": "41000.00",
        "stock": 4,
    },
    {
        "slug": "guitarra-electrica-tipo-strat",
        "name": "Guitarra eléctrica tipo Strat",
        "brand": "",
        "description": "Guitarra eléctrica de seis cuerdas para ensayo y escenario.",
        "category": "instrumentos",
        "price": "350000.00",
        "stock": 3,
    },
    {
        "slug": "guitarra-acustica-seis-cuerdas",
        "name": "Guitarra acústica de seis cuerdas",
        "brand": "",
        "description": "Guitarra acústica para tocar y componer.",
        "category": "instrumentos",
        "price": "220000.00",
        "stock": 4,
    },
    {
        "slug": "bajo-electrico-cuatro-cuerdas",
        "name": "Bajo eléctrico de cuatro cuerdas",
        "brand": "",
        "description": "Bajo eléctrico para ensayos y presentaciones.",
        "category": "instrumentos",
        "price": "390000.00",
        "stock": 2,
    },
    {
        "slug": "teclado-portatil",
        "name": "Teclado portátil",
        "brand": "",
        "description": "Teclado para practicar y componer.",
        "category": "instrumentos",
        "price": "280000.00",
        "stock": 2,
    },
    {
        "slug": "amplificador-guitarra-practica",
        "name": "Amplificador de guitarra para práctica",
        "brand": "",
        "description": "Amplificador compacto para practicar en casa.",
        "category": "amplificadores",
        "price": "150000.00",
        "stock": 4,
    },
    {
        "slug": "amplificador-bajo-ensayo",
        "name": "Amplificador de bajo para ensayo",
        "brand": "",
        "description": "Amplificador de bajo para ensayos.",
        "category": "amplificadores",
        "price": "240000.00",
        "stock": 2,
    },
    {
        "slug": "juego-cuerdas-guitarra-electrica",
        "name": "Juego de cuerdas para guitarra eléctrica",
        "brand": "",
        "description": "Juego de cuerdas de repuesto para guitarra eléctrica.",
        "category": "accesorios",
        "price": "12000.00",
        "stock": 12,
    },
    {
        "slug": "cable-instrumento",
        "name": "Cable para instrumento",
        "brand": "",
        "description": "Cable para conectar el instrumento al amplificador.",
        "category": "accesorios",
        "price": "18000.00",
        "stock": 10,
    },
    {
        "slug": "correa-guitarra",
        "name": "Correa para guitarra",
        "brand": "",
        "description": "Correa ajustable para guitarra o bajo.",
        "category": "accesorios",
        "price": "15000.00",
        "stock": 8,
    },
    {
        "slug": "pua-pack",
        "name": "Pack de púas",
        "brand": "",
        "description": "Púas para guitarra y bajo.",
        "category": "accesorios",
        "price": "5000.00",
        "stock": 15,
    },
)


class Command(BaseCommand):
    help = (
        "Carga productos de ejemplo de rock nacional y equipamiento. "
        "No modifica productos ni categorías existentes; los precios y el stock son ilustrativos."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for slug, name, sort_order in CATEGORIES:
            category, _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": name, "sort_order": sort_order}
            )
            categories[slug] = category

        created_count = 0
        for product_data in PRODUCTS:
            defaults = {
                **product_data,
                "category": categories[product_data["category"]],
            }
            slug = defaults.pop("slug")
            _, created = Product.objects.get_or_create(slug=slug, defaults=defaults)
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Productos creados: {created_count}. "
                f"Ya existentes, sin modificar: {len(PRODUCTS) - created_count}. "
                "Los precios y el stock son ilustrativos."
            )
        )
        inactive_categories = [category.name for category in categories.values() if not category.active]
        if inactive_categories:
            self.stdout.write(
                self.style.WARNING(
                    "Las siguientes categorías están inactivas y sus productos no se muestran "
                    f"en la tienda: {', '.join(inactive_categories)}."
                )
            )
