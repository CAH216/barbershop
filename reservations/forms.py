from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from datetime import date
import re
from .models import Barber, Service, Disponibilite, CodeSecretBarber


class BarberRegistrationForm(UserCreationForm):
    """Formulaire d'inscription pour les barbiers"""

    nom = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Nom'
    )
    prenom = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Prénom'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label='Email'
    )
    telephone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Téléphone'
    )
    code_secret = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Code secret fourni par l\'administrateur'
        }),
        label='Code secret'
    )

    class Meta:
        model = Barber
        fields = ['username', 'nom', 'prenom', 'email', 'telephone', 'password1', 'password2', 'code_secret']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean_code_secret(self):
        code = self.cleaned_data['code_secret']
        try:
            code_obj = CodeSecretBarber.objects.get(code=code, est_utilise=False)
            return code
        except CodeSecretBarber.DoesNotExist:
            raise ValidationError("Code secret invalide ou déjà utilisé")

    def clean_email(self):
        email = self.cleaned_data['email']
        if Barber.objects.filter(email=email).exists():
            raise ValidationError("Un barbier avec cet email existe déjà")
        return email


class ServiceForm(forms.ModelForm):
    """Formulaire pour ajouter/modifier un service"""

    class Meta:
        model = Service
        fields = ['titre', 'description', 'prix', 'duree_minutes', 'est_actif']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Coupe classique'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Décrivez votre service en détail...'
            }),
            'prix': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'duree_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '15',
                'step': '15'
            }),
            'est_actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'titre': 'Titre du service',
            'description': 'Description détaillée',
            'prix': 'Prix ($)',
            'duree_minutes': 'Durée (minutes)',
            'est_actif': 'Service actif'
        }
        help_texts = {
            'duree_minutes': 'Durée approximative du service (multiple de 15 minutes recommandé)',
            'est_actif': 'Décochez pour masquer temporairement ce service'
        }

    def clean_duree_minutes(self):
        duree = self.cleaned_data['duree_minutes']
        if duree < 15:
            raise ValidationError("La durée minimum est de 15 minutes")
        if duree > 480:  # 8 heures
            raise ValidationError("La durée maximum est de 8 heures")
        return duree

    def clean_prix(self):
        prix = self.cleaned_data['prix']
        if prix <= 0:
            raise ValidationError("Le prix doit être supérieur à 0")
        if prix > 999.99:
            raise ValidationError("Le prix ne peut pas dépasser 999.99€")
        return prix


class DisponibiliteForm(forms.ModelForm):
    """Formulaire pour ajouter des disponibilités"""

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='Services proposés pendant ce créneau'
    )

    class Meta:
        model = Disponibilite
        fields = ['type_disponibilite', 'date', 'jour_semaine', 'heure_debut', 'heure_fin', 'services']
        widgets = {
            'type_disponibilite': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'toggleDisponibiliteFields()'
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': date.today().isoformat()
            }),
            'jour_semaine': forms.Select(attrs={'class': 'form-control'}),
            'heure_debut': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'heure_fin': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
        }
        labels = {
            'type_disponibilite': 'Type de disponibilité',
            'date': 'Date (pour disponibilité précise)',
            'jour_semaine': 'Jour de la semaine (pour disponibilité récurrente)',
            'heure_debut': 'Heure de début',
            'heure_fin': 'Heure de fin',
        }

    def __init__(self, *args, **kwargs):
        barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)

        if barber:
            self.fields['services'].queryset = barber.services.filter(est_actif=True)
            self.fields['services'].required = True

    def clean(self):
        cleaned_data = super().clean()
        type_dispo = cleaned_data.get('type_disponibilite')
        date_dispo = cleaned_data.get('date')
        jour_semaine = cleaned_data.get('jour_semaine')
        heure_debut = cleaned_data.get('heure_debut')
        heure_fin = cleaned_data.get('heure_fin')
        services = cleaned_data.get('services')

        # Validation selon le type
        if type_dispo == 'precise':
            if not date_dispo:
                raise ValidationError("Date obligatoire pour une disponibilité précise")
            if date_dispo < date.today():
                raise ValidationError("La date ne peut pas être dans le passé")

        elif type_dispo == 'recurrente':
            if jour_semaine is None:
                raise ValidationError("Jour de semaine obligatoire pour une disponibilité récurrente")

        # Validation des heures
        if heure_debut and heure_fin:
            if heure_debut >= heure_fin:
                raise ValidationError("L'heure de début doit être antérieure à l'heure de fin")

            # Durée minimum de 30 minutes
            from datetime import datetime, timedelta
            debut = datetime.combine(date.today(), heure_debut)
            fin = datetime.combine(date.today(), heure_fin)
            if (fin - debut) < timedelta(minutes=30):
                raise ValidationError("La durée minimum est de 30 minutes")

        # Validation des services
        if not services:
            raise ValidationError("Vous devez sélectionner au moins un service")

        return cleaned_data


class ReservationClientForm(forms.Form):
    """Formulaire pour les clients qui réservent (sans inscription)"""

    nom = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom de famille'
        }),
        label='Nom *'
    )

    prenom = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre prénom'
        }),
        label='Prénom *'
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre.email@exemple.com'
        }),
        label='Email *',
        help_text='Pour recevoir la confirmation'
    )

    telephone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre numéro de téléphone (optionnel)'
        }),
        label='Téléphone'
    )

    accepter_conditions = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='J\'accepte les conditions de réservation',
        help_text='En cochant cette case, vous confirmez votre réservation'
    )

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        if len(nom) < 2:
            raise ValidationError("Le nom doit contenir au moins 2 caractères")
        return nom.title()

    def clean_prenom(self):
        prenom = self.cleaned_data['prenom'].strip()
        if len(prenom) < 2:
            raise ValidationError("Le prénom doit contenir au moins 2 caractères")
        return prenom.title()

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone', '')
        if telephone:
            telephone = telephone.strip()
            # Validation basique du numéro de téléphone
            pattern = r'^[\d\s\-\+\(\)\.]{8,20}$'
            if not re.match(pattern, telephone):
                raise ValidationError("Format de téléphone invalide")
        return telephone


class CodeSecretForm(forms.ModelForm):
    """Formulaire pour créer des codes secrets (admin seulement)"""

    class Meta:
        model = CodeSecretBarber
        fields = ['code', 'nom_barbershop']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code unique pour ce barbershop'
            }),
            'nom_barbershop': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du barbershop'
            })
        }
        labels = {
            'code': 'Code secret',
            'nom_barbershop': 'Nom du barbershop'
        }

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if len(code) < 6:
            raise ValidationError("Le code doit contenir au moins 6 caractères")
        return code


class FiltreReservationsForm(forms.Form):
    """Formulaire pour filtrer les réservations"""

    STATUT_CHOICES = [
        ('', 'Tous les statuts'),
        ('confirmee', 'Confirmées'),
        ('annulee', 'Annulées'),
        ('terminee', 'Terminées'),
    ]

    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de début'
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de fin'
    )

    statut = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Statut'
    )

    client_recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom ou email du client'
        }),
        label='Rechercher un client'
    )