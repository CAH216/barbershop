from django.shortcuts import render
from django.http import HttpResponseNotFound, HttpResponseServerError, HttpResponseForbidden


def handler404(request, exception):
    """Vue personnalisée pour les erreurs 404"""
    return render(request, 'error.html', status=404)
