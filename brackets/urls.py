from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('place_bet/<int:team_id>/', views.place_bet, name='place_bet'),
    path('get_odds/', views.get_odds, name='get_odds'),
]