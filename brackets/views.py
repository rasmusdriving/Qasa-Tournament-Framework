from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Tournament, Team, Bet
from django.db.models import Sum

def index(request):
    active_tournament = Tournament.objects.filter(is_active=True).first()
    if active_tournament:
        teams = Team.objects.filter(tournament=active_tournament)
        odds = calculate_odds(active_tournament)
        return render(request, 'brackets/index.html', {'tournament': active_tournament, 'teams': teams, 'odds': odds})
    return render(request, 'brackets/index.html', {'message': 'No active tournament'})

def place_bet(request, team_id):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        amount = request.POST.get('amount')
        team = Team.objects.get(id=team_id)
        tournament = team.tournament
        Bet.objects.create(name=name, email=email, amount=amount, team=team, tournament=tournament)
        return redirect('index')
    team = Team.objects.get(id=team_id)
    return render(request, 'brackets/place_bet.html', {'team': team})

def calculate_odds(tournament):
    teams = Team.objects.filter(tournament=tournament)
    total_bets = Bet.objects.filter(tournament=tournament).aggregate(Sum('amount'))['amount__sum'] or 0
    odds = {}
    for team in teams:
        team_bets = Bet.objects.filter(team=team).aggregate(Sum('amount'))['amount__sum'] or 0
        if team_bets > 0:
            odds[team.name] = round(total_bets / team_bets, 2)
        else:
            odds[team.name] = 0
    return odds

def get_odds(request):
    active_tournament = Tournament.objects.filter(is_active=True).first()
    if active_tournament:
        odds = calculate_odds(active_tournament)
        return JsonResponse(odds)
    return JsonResponse({})