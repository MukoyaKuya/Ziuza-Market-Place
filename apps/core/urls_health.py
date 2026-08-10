from django.urls import path
from .views import LivenessHealthView, ReadinessHealthView

app_name = 'health'

urlpatterns = [
    path('live/', LivenessHealthView.as_view(), name='live'),
    path('ready/', ReadinessHealthView.as_view(), name='ready'),
]
