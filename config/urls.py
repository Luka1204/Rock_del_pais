"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import include
from django.contrib import admin
from django.urls import include, path
from store import views

urlpatterns = [
    path("", views.home, name="home"),
    path("admin/login/", views.admin_login, name="admin_login_otp"),
    path("admin/", admin.site.urls),
    path("management/", views.management_home, name="management_home"),
    path("management/products/", views.management_product_list, name="management_product_list"),
    path("management/orders/", views.management_order_list, name="management_order_list"),
    path("management/users/", views.management_user_list, name="management_user_list"),
    path("management/consultations/", views.management_consultation_list, name="management_consultation_list"),
    path("management/categories/", views.management_category_list, name="management_category_list"),
    path("management/categories/create/", views.category_create, name="category_create"),
    path("management/categories/edit/<int:pk>/", views.category_edit, name="category_edit"),
    path("management/categories/delete/<int:pk>/", views.category_delete, name="category_delete"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("login/", views.login_view, name="login"),
    path("verify-email-code/", views.verify_email_code, name="verify_email_code"),
    path("verify-email-code/resend/", views.resend_email_code, name="resend_email_code"),

    # Rutas del CRUD de productos:
    path("productos/", views.producto_lista, name="producto_lista"),
    path("productos/nuevo/", views.producto_crear, name="producto_crear"),
    path("productos/<int:pk>/", views.producto_detalle, name="producto_detalle"),
    path("productos/<int:pk>/editar/", views.producto_editar, name="producto_editar"),
    path("productos/<int:pk>/eliminar/", views.producto_eliminar, name="producto_eliminar"),
    path("contact/", views.contact_view, name="contact"),
]
