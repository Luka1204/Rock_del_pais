from django.contrib import admin
from .models import Category, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "stock", "active", "created_at")
    list_filter = ("active", "category")
    search_fields = ("name", "description")


admin.site.register(Category)