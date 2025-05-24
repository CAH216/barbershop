from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import datetime, date, timedelta
from .models import Barber, Service, Disponibilite, Reservation, Client, CodeSecretBarber
from .forms import BarberRegistrationForm, ServiceForm, DisponibiliteForm, ReservationClientForm
import json


def index(request):
    """Page d'accueil - Liste des barbiers et leurs services"""
    barbiers = Barber.objects.all()
    services_par_barbier = {}

    for barbier in barbiers:
        services_par_barbier[barbier.id] = barbier.services.filter(est_actif=True)

    return render(request, 'index.html', {
        'barbiers': barbiers,
        'services_par_barbier': services_par_barbier
    })


def inscription_barber(request):
    """Inscription des barbiers avec code secret"""
    if request.method == 'POST':
        form = BarberRegistrationForm(request.POST)
        if form.is_valid():
            # Vérifier le code secret
            code_secret = form.cleaned_data['code_secret']
            try:
                code_obj = CodeSecretBarber.objects.get(code=code_secret, est_utilise=False)

                # Créer le barbier
                barber = form.save(commit=False)
                barber.barbershop_name = code_obj.nom_barbershop
                barber.save()

                # Marquer le code comme utilisé
                code_obj.est_utilise = True
                code_obj.date_utilisation = timezone.now()
                code_obj.barber = barber
                code_obj.save()

                # Connecter automatiquement
                login(request, barber)
                messages.success(request, f"Inscription réussie ! Bienvenue {barber.prenom}")
                return redirect('dashboard_barber')

            except CodeSecretBarber.DoesNotExist:
                messages.error(request, "Code secret invalide ou déjà utilisé")
    else:
        form = BarberRegistrationForm()

    return render(request, 'inscription_barber.html', {'form': form})


@login_required
def dashboard_barber(request):
    """Dashboard pour les barbiers"""
    # Services du barbier
    services = request.user.services.all()

    # Disponibilités du barbier
    disponibilites = Disponibilite.objects.filter(barber=request.user).order_by('date', 'heure_debut')

    # Réservations récentes
    reservations = Reservation.objects.filter(
        barber=request.user,
        statut='confirmee'
    ).order_by('date_reservation', 'heure_debut')[:10]

    # Statistiques
    stats = {
        'services_actifs': services.filter(est_actif=True).count(),
        'reservations_aujourd_hui': Reservation.objects.filter(
            barber=request.user,
            date_reservation=date.today(),
            statut='confirmee'
        ).count(),
        'reservations_semaine': Reservation.objects.filter(
            barber=request.user,
            date_reservation__gte=date.today(),
            date_reservation__lt=date.today() + timedelta(days=7),
            statut='confirmee'
        ).count(),
    }

    context = {
        'services': services,
        'disponibilites': disponibilites,
        'reservations': reservations,
        'stats': stats
    }

    return render(request, 'dashboard_barber.html', context)


@login_required
def ajouter_service(request):
    """Ajouter un nouveau service"""
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.barber = request.user
            service.save()
            messages.success(request, f"Service '{service.titre}' ajouté avec succès")
            return redirect('dashboard_barber')
    else:
        form = ServiceForm()

    return render(request, 'ajouter_service.html', {'form': form})


@login_required
def modifier_service(request, service_id):
    """Modifier un service existant"""
    service = get_object_or_404(Service, id=service_id, barber=request.user)

    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service '{service.titre}' modifié avec succès")
            return redirect('dashboard_barber')
    else:
        form = ServiceForm(instance=service)

    return render(request, 'modifier_service.html', {'form': form, 'service': service})


@login_required
def ajouter_disponibilite(request):
    """Ajouter une disponibilité"""
    if request.method == 'POST':
        form = DisponibiliteForm(request.POST, barber=request.user)
        if form.is_valid():
            disponibilite = form.save(commit=False)
            disponibilite.barber = request.user
            disponibilite.save()

            # Associer les services sélectionnés
            services_ids = form.cleaned_data['services']
            disponibilite.services.set(services_ids)

            messages.success(request, "Disponibilité ajoutée avec succès")
            return redirect('dashboard_barber')
    else:
        form = DisponibiliteForm(barber=request.user)

    return render(request, 'ajouter_disponibilite.html', {'form': form})


def voir_services_barbier(request, barber_id):
    """Voir les services d'un barbier"""
    barber = get_object_or_404(Barber, id=barber_id)
    services = barber.services.filter(est_actif=True)

    return render(request, 'voir_services_barbier.html', {
        'barber': barber,
        'services': services
    })


def voir_disponibilites_service(request, service_id):
    """Voir les disponibilités pour un service"""
    service = get_object_or_404(Service, id=service_id, est_actif=True)
    barber = service.barber

    # Générer disponibilités récurrentes pour les 30 prochains jours
    date_debut = date.today()
    date_fin = date_debut + timedelta(days=30)
    Disponibilite.objects.generer_disponibilites_recurrentes(barber, date_debut, date_fin)

    # Récupérer disponibilités disponibles pour ce service
    disponibilites = Disponibilite.objects.filter(
        services=service,
        est_disponible=True,
        date__gte=date.today()
    ).order_by('date', 'heure_debut')

    return render(request, 'voir_disponibilites_service.html', {
        'service': service,
        'barber': barber,
        'disponibilites': disponibilites
    })


def reserver_service(request, service_id, disponibilite_id):
    """Page de réservation d'un service"""
    service = get_object_or_404(Service, id=service_id, est_actif=True)
    disponibilite = get_object_or_404(Disponibilite, id=disponibilite_id, est_disponible=True)

    # Vérifier que la disponibilité est bien liée au service
    if service not in disponibilite.services.all():
        messages.error(request, "Cette disponibilité n'est pas valide pour ce service")
        return redirect('voir_disponibilites_service', service_id=service_id)

    if request.method == 'POST':
        form = ReservationClientForm(request.POST)
        if form.is_valid():
            # Créer ou récupérer le client
            client_data = {
                'nom': form.cleaned_data['nom'],
                'prenom': form.cleaned_data['prenom'],
                'email': form.cleaned_data['email'],
                'telephone': form.cleaned_data.get('telephone', '')
            }

            client, created = Client.objects.get_or_create(
                email=client_data['email'],
                defaults=client_data
            )

            # Si client existe déjà, mettre à jour ses infos
            if not created:
                for key, value in client_data.items():
                    setattr(client, key, value)
                client.save()

            # Calculer heure de fin
            debut = datetime.combine(date.today(), disponibilite.heure_debut)
            fin = debut + timedelta(minutes=service.duree_minutes)
            heure_fin = fin.time()

            # Créer la réservation
            try:
                reservation = Reservation(
                    client=client,
                    barber=service.barber,
                    service=service,
                    disponibilite=disponibilite,
                    date_reservation=disponibilite.date,
                    heure_debut=disponibilite.heure_debut,
                    heure_fin=heure_fin,
                    prix_service=service.prix
                )
                reservation.save()

                return render(request, 'confirmation_reservation.html', {
                    'reservation': reservation,
                    'service': service,
                    'client': client
                })

            except Exception as e:
                messages.error(request, f"Erreur lors de la réservation : {e}")
    else:
        form = ReservationClientForm()

    return render(request, 'reserver_service.html', {
        'service': service,
        'disponibilite': disponibilite,
        'form': form
    })


def confirmer_reservation(request, reservation_id):
    """Page de confirmation finale de la réservation"""
    reservation = get_object_or_404(Reservation, numero_reservation=reservation_id)

    if request.method == 'POST':
        if 'confirmer' in request.POST:
            # La réservation est déjà créée, juste envoyer l'email
            messages.success(request,
                             f"Réservation confirmée ! Un email a été envoyé au barbier. "
                             f"Numéro de réservation : {reservation.numero_reservation}")
            return redirect('index')
        else:
            # Annuler la réservation
            reservation.delete()
            # Remettre la disponibilité
            reservation.disponibilite.est_disponible = True
            reservation.disponibilite.save()
            messages.info(request, "Réservation annulée")
            return redirect('index')

    return render(request, 'confirmer_reservation.html', {
        'reservation': reservation
    })


@login_required
def mes_reservations(request):
    """Voir les réservations reçues (pour les barbiers)"""
    reservations = Reservation.objects.filter(
        barber=request.user
    ).order_by('-date_creation')

    return render(request, 'mes_reservations.html', {'reservations': reservations})


@login_required
@require_POST
def changer_statut_reservation(request, reservation_id):
    """Changer le statut d'une réservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id, barber=request.user)
    nouveau_statut = request.POST.get('statut')

    if nouveau_statut in ['confirmee', 'annulee', 'terminee']:
        reservation.statut = nouveau_statut
        reservation.save()

        # Si annulée, remettre la disponibilité
        if nouveau_statut == 'annulee':
            reservation.disponibilite.est_disponible = True
            reservation.disponibilite.save()

        messages.success(request, f"Réservation {nouveau_statut}")

    return redirect('mes_reservations')


def api_disponibilites_service(request, service_id):
    """API pour récupérer disponibilités d'un service en JSON"""
    service = get_object_or_404(Service, id=service_id, est_actif=True)

    # Générer disponibilités récurrentes
    date_debut = date.today()
    date_fin = date_debut + timedelta(days=30)
    Disponibilite.objects.generer_disponibilites_recurrentes(service.barber, date_debut, date_fin)

    disponibilites = Disponibilite.objects.filter(
        services=service,
        est_disponible=True,
        date__gte=date.today()
    ).order_by('date', 'heure_debut')

    data = []
    for dispo in disponibilites:
        data.append({
            'id': dispo.id,
            'date': dispo.date.strftime('%Y-%m-%d'),
            'heure_debut': dispo.heure_debut.strftime('%H:%M'),
            'heure_fin': dispo.heure_fin.strftime('%H:%M'),
            'jour': dispo.date.strftime('%A')
        })

    return JsonResponse({'disponibilites': data})