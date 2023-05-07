from django.urls import path
from .views import rbot_view

urlpatterns = [
    path('', rbot_view, name='rbot_view'),
]
