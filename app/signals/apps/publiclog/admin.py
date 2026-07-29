# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.contrib import admin

from signals.apps.publiclog.models import Blocklist, ReporterLog


class BlocklistAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_display = ('ip_network', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    ordering = ('ip_network',)
    search_fields = ('ip_network', 'description')


class ReporterLogAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_display = ('signal', 'ip_address', 'user_agent', 'created_at')
    list_filter = ('created_at',)
    list_select_related = ('signal',)
    ordering = ('-created_at',)
    readonly_fields = ('signal', 'ip_address', 'user_agent', 'created_at')
    search_fields = ('signal__id__exact', 'ip_address', 'user_agent')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Blocklist, BlocklistAdmin)
admin.site.register(ReporterLog, ReporterLogAdmin)
