"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
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
from django.views.generic import TemplateView   
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings

superuser_required = user_passes_test(
    lambda u: u.is_active and u.is_superuser,
    login_url="/admin/login/",
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("accounts.urls")),
    path("", TemplateView.as_view(template_name="list.html"), name="home"),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login"),
    path("new/", TemplateView.as_view(template_name="form.html"), name="new"),
    path("edit/<int:pk>/", TemplateView.as_view(template_name="form.html"), name="edit"),
     path("register/", TemplateView.as_view(template_name="register.html"), name="register"),
    path("", include("articles.urls")),
    path("api/schema/", superuser_required(SpectacularAPIView.as_view()), name="schema"),
    path(
        "api/docs/",
        superuser_required(SpectacularSwaggerView.as_view(url_name="schema")),
        name="swagger-ui",
    ),
]
if settings.DEBUG:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]