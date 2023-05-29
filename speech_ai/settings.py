import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-zp@37@07d1dh$2-n5ghq$*-!dcpbc!5hmr(p-z26&+i6&5(@jb'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'speach.apps.SpeachConfig',
    'login.apps.LoginConfig',
    'WoofWaf',
    'judge',
    'captcha',
    'stats',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'stats.middleware.StatsMiddleware',
    'WoofWaf.WafMiddleware.WafMiddleware.MyTestMiddleware_first',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'speech_ai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # 'DIRS': [],
        'DIRS': [
                os.path.join(BASE_DIR, 'judge/templates').replace('\\', '/'),
                os.path.join(BASE_DIR, 'login/templates').replace('\\', '/'),
                os.path.join(BASE_DIR, 'speach/templates').replace('\\', '/'),
                os.path.join(BASE_DIR, 'WoofWaf/templates').replace('\\', '/'),
            ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'builtins': [
                'django.templatetags.static',
            ],
            'libraries': {
                # Adding this section should work around the issue.
                'staticfiles': 'django.templatetags.static',
            },
        },
    },
]

WSGI_APPLICATION = 'speech_ai.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'speech_score',
        'USER': 'root',
        'PASSWORD': 'Kosm133164',
        'HOST': '127.0.0.1',
        'PORT': 3306,
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'zh-hans'  # en-us
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_L10N = True
USE_TZ = False


STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static").replace('\\', '/')

# STATICFILES_DIRS = (
#     os.path.join(BASE_DIR, "judge/static").replace('\\', '/'),
#     os.path.join(BASE_DIR, "login/static").replace('\\', '/'),
#     os.path.join(BASE_DIR, "speach/static").replace('\\', '/'),
#     os.path.join(BASE_DIR, 'WoofWaf/static').replace('\\', '/'),
# )

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'

ADMINS = [('Gongzijun', 'gongzijun2020@163.com')]
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 设置文件保存路径
MEDIA_ROOT = os.path.join(BASE_DIR, 'media').replace('\\', '/')
MEDIA_URL = '/media/'

