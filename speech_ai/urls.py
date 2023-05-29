from django.contrib import admin
from django.urls import path, include
from login.views import page_not_found
from django.conf.urls import url

from django.views import static
from speech_ai.settings import STATIC_ROOT, MEDIA_ROOT

urlpatterns = [

    path('admin/', admin.site.urls),
    path('', include('speach.urls')),
    path('login/', include('login.urls')),
    path('Administrator/', include('WoofWaf.urls')),
    path('judge/',include('judge.urls')),
    # path('stats/',include('stats.urls')),
    url(r'^captcha', include('captcha.urls')),

    url('^static/(?P<path>.*)$', static.serve, {'document_root': STATIC_ROOT}, name='static'),
    url('^media/(?P<path>.*)$', static.serve, {'document_root': MEDIA_ROOT}, name='media'),

]
# handler404 = page_not_found

