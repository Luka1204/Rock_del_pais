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
from django.contrib import admin
from django.urls import path
from store import views

urlpatterns = [
    path("", views.home, name="home"),
    path('admin/', admin.site.urls),
    path('management/categories/', views.management_category_list, name='management_category_list'),
    path('management/categories/create/', views.category_create, name='category_create'),
    path('management/categories/edit/<int:pk>/', views.category_edit, name='category_edit'),
    path('management/categories/delete/<int:pk>/', views.category_delete, name='category_delete'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout')
]
