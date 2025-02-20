from django.urls import path
from .views import DashBoardAPIView

urlpatterns = [
    path('home/dashboard/', DashBoardAPIView.as_view(), name='dashboard'),
]
