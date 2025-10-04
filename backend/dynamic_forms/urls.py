# """
# URL configuration for dynamic_forms project.

# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/4.2/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
# from django.contrib import admin
# from django.urls import path

# urlpatterns = [
#     path("admin/", admin.site.urls),
# ]

# backend/dynamic_forms/urls.py - MAIN URLS FILE
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok", "message": "Dynamic Forms API is running"})

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Health check
    path('health/', health_check, name='health-check'),
    
    # API endpoints
    path('api/users/', include('apps.users.urls')),
    path('api/forms/', include('apps.forms.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    
    # API root
    path('api/', lambda request: JsonResponse({
        "message": "Dynamic Forms API",
        "version": "1.0.0",
        "endpoints": {
            "users": "/api/users/",
            "forms": "/api/forms/",
            "notifications": "/api/notifications/",
            "admin": "/admin/",
            "health": "/health/"
        }
    })),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handlers
handler404 = lambda request, exception: JsonResponse({"error": "Not found"}, status=404)
handler500 = lambda request: JsonResponse({"error": "Internal server error"}, status=500)
