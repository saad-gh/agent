from django.contrib import admin
from .models import (
    AgentRun, AgentMessage, JinjaHelper, GeneratedFunction,
    ManualStep, ModelPreference, ApiDocumentation, AiUsageLog
)


class AgentMessageInline(admin.TabularInline):
    model = AgentMessage
    extra = 0
    readonly_fields = ['sequence', 'role', 'tool_name', 'tool_args', 'content', 'token_usage']


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'status', 'model', 'iteration_count', 'created_at', 'updated_at']
    list_filter = ['status', 'organization']
    search_fields = ['prompt', 'model']
    inlines = [AgentMessageInline]


@admin.register(JinjaHelper)
class JinjaHelperAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'is_approved', 'created_at', 'updated_at']
    list_filter = ['is_approved']
    search_fields = ['name', 'source']
    readonly_fields = ['source_hash']


@admin.register(GeneratedFunction)
class GeneratedFunctionAdmin(admin.ModelAdmin):
    list_display = ['slug', 'version', 'is_approved', 'created_at', 'updated_at']
    list_filter = ['is_approved']
    search_fields = ['slug', 'source']
    readonly_fields = ['source_hash']


@admin.register(ManualStep)
class ManualStepAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'status', 'description', 'created_at']
    list_filter = ['status', 'organization']
    search_fields = ['description']


@admin.register(ModelPreference)
class ModelPreferenceAdmin(admin.ModelAdmin):
    list_display = ['organization', 'reasoning_tier', 'resource']
    list_filter = ['reasoning_tier', 'organization']


@admin.register(ApiDocumentation)
class ApiDocumentationAdmin(admin.ModelAdmin):
    list_display = ['name', 'service', 'version', 'doc_type', 'doc_source', 'verified', 'processing_status', 'is_latest']
    list_filter = ['doc_type', 'doc_source', 'verified', 'processing_status', 'is_latest']
    search_fields = ['name', 'service__name', 'version']


@admin.register(AiUsageLog)
class AiUsageLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'service', 'ai_model', 'total_tokens', 'success', 'timestamp']
    list_filter = ['service', 'success', 'is_billable', 'timestamp']
    search_fields = ['ai_model', 'user_prompt']
    readonly_fields = ['timestamp']
