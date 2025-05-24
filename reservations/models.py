from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, date, time, timedelta
import uuid


class CodeSecretBarber(models.Model):
    """Codes secrets pour l'inscription des barbiers"""
    code = models.CharField(max_length=50, unique=True)
    nom_barbershop = models.CharField(max_length=255)
    est_utilise = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_utilisation = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Code {self.code} - {self.nom_barbershop}"


class Barber(AbstractUser):
    """Modèle pour les barbiers uniquement"""
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    barbershop_name = models.CharField(max_length=255)
    code_secret_utilise = models.ForeignKey(CodeSecretBarber, on_delete=models.SET_NULL, null=True, blank=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    # Résoudre les conflits avec le modèle User par défaut
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='barber_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='barber_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return f"{self.prenom} {self.nom} - {self.barbershop_name}"


class Service(models.Model):
    """Services proposés par le barbier"""
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='services')
    titre = models.CharField(max_length=200)
    description = models.TextField()
    prix = models.DecimalField(max_digits=6, decimal_places=2)
    duree_minutes = models.IntegerField(help_text="Durée du service en minutes")
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['prix']

    def __str__(self):
        return f"{self.titre} - {self.prix}€ ({self.barber.barbershop_name})"


class DisponibiliteManager(models.Manager):
    """Manager pour générer les disponibilités récurrentes"""

    def generer_disponibilites_recurrentes(self, barber, date_debut, date_fin):
        """Génère les disponibilités récurrentes pour une période donnée"""
        disponibilites_recurrentes = self.filter(
            barber=barber,
            type_disponibilite='recurrente'
        )

        nouvelles_disponibilites = []
        date_courante = date_debut

        while date_courante <= date_fin:
            jour_semaine = date_courante.weekday()

            # Chercher disponibilités récurrentes pour ce jour
            for dispo_recurrente in disponibilites_recurrentes.filter(jour_semaine=jour_semaine):
                # Vérifier si pas déjà créée pour cette date
                if not self.filter(
                        barber=barber,
                        date=date_courante,
                        heure_debut=dispo_recurrente.heure_debut,
                        heure_fin=dispo_recurrente.heure_fin
                ).exists():
                    # Créer nouvelle disponibilité
                    nouvelle_dispo = self.model(
                        barber=barber,
                        type_disponibilite='precise',
                        date=date_courante,
                        heure_debut=dispo_recurrente.heure_debut,
                        heure_fin=dispo_recurrente.heure_fin,
                        est_disponible=True
                    )
                    nouvelle_dispo.save()

                    # Ajouter les mêmes services
                    nouvelle_dispo.services.set(dispo_recurrente.services.all())
                    nouvelles_disponibilites.append(nouvelle_dispo)

            date_courante += timedelta(days=1)

        return len(nouvelles_disponibilites)


class Disponibilite(models.Model):
    """Disponibilités des barbiers liées aux services"""
    JOUR_CHOICES = [
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
        (6, 'Dimanche'),
    ]

    TYPE_CHOICES = [
        ('precise', 'Date précise'),
        ('recurrente', 'Récurrente'),
    ]

    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='disponibilites')
    services = models.ManyToManyField(Service, related_name='disponibilites')
    type_disponibilite = models.CharField(max_length=15, choices=TYPE_CHOICES, default='precise')

    # Pour disponibilité précise
    date = models.DateField(null=True, blank=True)

    # Pour disponibilité récurrente
    jour_semaine = models.IntegerField(choices=JOUR_CHOICES, null=True, blank=True)

    # Heures
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    # Statut
    est_disponible = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    # Ajouter le manager personnalisé
    objects = DisponibiliteManager()

    def __str__(self):
        services_noms = ", ".join([s.titre for s in self.services.all()])
        if self.type_disponibilite == 'precise' and self.date:
            return f"{self.barber} - {self.date} ({self.heure_debut}-{self.heure_fin}) - Services: {services_noms}"
        else:
            return f"{self.barber} - {self.get_jour_semaine_display()} ({self.heure_debut}-{self.heure_fin}) - Services: {services_noms}"

    def save(self, *args, **kwargs):
        # Validation : si type précis, date obligatoire
        if self.type_disponibilite == 'precise' and not self.date:
            raise ValueError("Date obligatoire pour disponibilité précise")
        # Si type récurrent, jour_semaine obligatoire
        if self.type_disponibilite == 'recurrente' and self.jour_semaine is None:
            raise ValueError("Jour de semaine obligatoire pour disponibilité récurrente")
        super().save(*args, **kwargs)


class Client(models.Model):
    """Modèle simple pour les clients (pas d'inscription)"""
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.email})"


class Reservation(models.Model):
    """Réservations des clients"""
    STATUS_CHOICES = [
        ('confirmee', 'Confirmée'),
        ('annulee', 'Annulée'),
        ('terminee', 'Terminée'),
    ]

    # ID unique pour suivi
    numero_reservation = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Participants
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='reservations')
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='reservations_recues')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reservations')
    disponibilite = models.ForeignKey(Disponibilite, on_delete=models.CASCADE, related_name='reservations')

    # Détails de la réservation
    date_reservation = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    # Statut et métadonnées
    statut = models.CharField(max_length=15, choices=STATUS_CHOICES, default='confirmee')
    date_creation = models.DateTimeField(auto_now_add=True)

    # Prix au moment de la réservation
    prix_service = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = ['barber', 'date_reservation', 'heure_debut']
        ordering = ['-date_creation']

    def __str__(self):
        return f"Réservation {self.numero_reservation} - {self.client} pour {self.service.titre} le {self.date_reservation}"

    def save(self, *args, **kwargs):
        # Sauvegarder le prix au moment de la réservation
        if not self.prix_service:
            self.prix_service = self.service.prix

        # Calculer heure de fin basée sur la durée du service
        if not self.heure_fin:
            debut = datetime.combine(date.today(), self.heure_debut)
            fin = debut + timedelta(minutes=self.service.duree_minutes)
            self.heure_fin = fin.time()

        super().save(*args, **kwargs)

        # Envoyer email de confirmation au barbier
        if self.pk and self.statut == 'confirmee':
            self.envoyer_email_barbier()

        # Marquer disponibilité comme non disponible
        if self.disponibilite and self.statut == 'confirmee':
            self.disponibilite.est_disponible = False
            self.disponibilite.save()

    def envoyer_email_barbier(self):
        """Envoie email de notification au barbier"""
        try:
            sujet = f"Nouvelle réservation - {self.service.titre} - {self.date_reservation.strftime('%d/%m/%Y')}"
            message = f"""
Bonjour {self.barber.prenom},

Vous avez une nouvelle réservation :

👤 Client : {self.client.prenom} {self.client.nom}
📧 Email : {self.client.email}
{f'📞 Téléphone : {self.client.telephone}' if self.client.telephone else ''}

💈 Service : {self.service.titre}
💰 Prix : {self.prix_service}€
🗓️ Date : {self.date_reservation.strftime('%d/%m/%Y')}
⏰ Heure : {self.heure_debut.strftime('%H:%M')} - {self.heure_fin.strftime('%H:%M')}

📝 Description du service : {self.service.description}

Numéro de réservation : {self.numero_reservation}

Cordialement,
{settings.SITE_NAME}
            """

            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.barber.email],
                fail_silently=False,
            )

        except Exception as e:
            print(f"Erreur envoi email : {e}")