from django.urls import path
from . import views

urlpatterns=[
    path('chat/<int:order_id>/', views.chat, name='chat'),
    path('dashboard/', views.dashboard, name='dashboard'),
]