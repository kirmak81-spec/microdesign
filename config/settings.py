import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "1") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only-change-before-deployment")
if not DEBUG and SECRET_KEY.startswith("local-development"):
    raise RuntimeError("Set SECRET_KEY in production")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "shop",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shop.context.store",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}
if os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "NAME": os.getenv("POSTGRES_DB", "microdesign"),
            "USER": os.getenv("POSTGRES_USER", "microdesign"),
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/account/login/"
LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
CSRF_TRUSTED_ORIGINS = [
    x for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x
]
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
ROBOKASSA_LOGIN = os.getenv("ROBOKASSA_LOGIN", "")
ROBOKASSA_PASSWORD1 = os.getenv("ROBOKASSA_PASSWORD1", "")
ROBOKASSA_PASSWORD2 = os.getenv("ROBOKASSA_PASSWORD2", "")
ROBOKASSA_TEST = os.getenv("ROBOKASSA_TEST", "1") == "1"
ROBOKASSA_HASH = os.getenv("ROBOKASSA_HASH", "sha256")
# Live checkout stays disabled until delivery prices, fiscal receipt and credentials are approved.
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "0") == "1"
