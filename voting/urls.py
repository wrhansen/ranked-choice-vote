from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("poll/<uuid:pk>/", views.poll_detail, name="poll-detail"),
    path("poll/<uuid:pk>/join/", views.join, name="poll-join"),
    path("poll/<uuid:pk>/vote/", views.vote, name="poll-vote"),
    path("poll/<uuid:pk>/vote/amend/", views.vote_amend, name="poll-vote-amend"),
    path("poll/<uuid:pk>/stream/", views.poll_stream, name="poll-stream"),
]
