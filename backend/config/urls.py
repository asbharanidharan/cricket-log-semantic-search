
from django.contrib import admin
from django.urls import path

from search_api.views import search_cricket_logs, chat_cricket_logs

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/search/", search_cricket_logs, name="search-cricket-logs"),
    path("api/chat/", chat_cricket_logs, name="chat-cricket-logs"),
]
