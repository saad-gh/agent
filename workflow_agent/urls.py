from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('task/', include('workflow_orchestrator.urls')),

    # Agent API endpoints
    path('agent/run/', views.start_agent_run_view, name='start_agent_run'),
    path('agent/run/<int:run_id>/', views.get_agent_run_view, name='get_agent_run'),
    path('agent/run/<int:run_id>/message/', views.answer_agent_run_view, name='answer_agent_run'),
    path('agent/run/<int:run_id>/approve/', views.approve_agent_plan_view, name='approve_agent_plan'),
    path('agent/step/<int:step_id>/approve/', views.approve_manual_step_view, name='approve_manual_step'),
]
