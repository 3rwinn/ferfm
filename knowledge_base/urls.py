from django.urls import path
from . import views

app_name = 'knowledge_base'

urlpatterns = [
    path('query/', views.QueryKnowledgeView.as_view(), name='query_knowledge'),
] 