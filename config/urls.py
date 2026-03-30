from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('secret-admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('staff/', include('staff.urls')),
    path('academics/', include('academics.urls')),
    path('examinations/', include('examinations.urls')),
    path('results/', include('results.urls')),
    path('schemes/', include('schemes.urls')),
    path('timetable/', include('timetable.urls')),
    path('promotions/', include('promotions.urls')),
    path('portal/', include('portal.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)