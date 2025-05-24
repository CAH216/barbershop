# barbershop/urls.py (URLs principales)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from reservations import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Pages principales
    path('', views.index, name='index'),
    
    # Authentification barbiers
    path('inscription/', views.inscription_barber, name='inscription_barber'),
    path('connexion/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('deconnexion/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Dashboard barbier
    path('dashboard/', views.dashboard_barber, name='dashboard_barber'),
    
    # Gestion des services
    path('services/ajouter/', views.ajouter_service, name='ajouter_service'),
    path('services/<int:service_id>/modifier/', views.modifier_service, name='modifier_service'),
    
    # Gestion des disponibilités
    path('disponibilites/ajouter/', views.ajouter_disponibilite, name='ajouter_disponibilite'),
    
    # Côté client
    path('barbier/<int:barber_id>/services/', views.voir_services_barbier, name='voir_services_barbier'),
    path('service/<int:service_id>/disponibilites/', views.voir_disponibilites_service, name='voir_disponibilites_service'),
    path('service/<int:service_id>/reserver/<int:disponibilite_id>/', views.reserver_service, name='reserver_service'),
    path('confirmation/<uuid:reservation_id>/', views.confirmer_reservation, name='confirmer_reservation'),
    
    # Gestion des réservations
    path('reservations/', views.mes_reservations, name='mes_reservations'),
    path('reservations/<int:reservation_id>/statut/', views.changer_statut_reservation, name='changer_statut_reservation'),
    
    # API
    path('api/service/<int:service_id>/disponibilites/', views.api_disponibilites_service, name='api_disponibilites_service'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

