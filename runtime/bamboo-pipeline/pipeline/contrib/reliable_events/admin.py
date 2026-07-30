# -*- coding: utf-8 -*-
from django.contrib import admin

from pipeline.contrib.reliable_events.models import EngineEventInbox, EngineEventLane


@admin.register(EngineEventInbox)
class EngineEventInboxAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "mode", "status", "root_pipeline_id", "node_id", "version", "accepted_at")
    list_filter = ("mode", "status", "event_type")
    search_fields = ("idempotency_key", "root_pipeline_id", "node_id")
    readonly_fields = [f.name for f in EngineEventInbox._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EngineEventLane)
class EngineEventLaneAdmin(admin.ModelAdmin):
    list_display = ("id", "concurrency_key", "lease_owner", "lease_generation", "lease_until", "last_progress_at")
    search_fields = ("concurrency_key",)
    readonly_fields = [f.name for f in EngineEventLane._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
