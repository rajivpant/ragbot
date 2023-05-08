from django.urls import path
from . import views

app_name = 'rbot_app'

urlpatterns = [
    path('', views.get_response, name='get_response'),
]
