from django.contrib import admin
from .models import Tournament, Team, Player, Bet

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    actions = ['set_active']

    def set_active(self, request, queryset):
        queryset.update(is_active=True)
        Tournament.objects.exclude(pk__in=queryset).update(is_active=False)
    set_active.short_description = "Set selected tournament as active"

admin.site.register(Team)
admin.site.register(Player)
admin.site.register(Bet)