from django.contrib import admin
from .models import Actu

@admin.register(Actu)
class ActuAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_short_text', 'created_at')
    search_fields = ('text',)
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

    def get_short_text(self, obj):
        return obj.text[:75] + '...' if len(obj.text) > 75 else obj.text
    get_short_text.short_description = 'Text (Shortened)'
