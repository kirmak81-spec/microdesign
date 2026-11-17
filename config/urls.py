from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from shop import views

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("products/<slug:slug>/", views.product, name="product"),
    path("news/", views.news_list, name="news_list"),
    path("news/<str:slug>/", views.news_detail, name="news_detail"),
    path("info/<slug:slug>/", views.page, name="page"),
    path("cart/", views.cart, name="cart"),
    path("cart/<int:pk>/", views.cart_update, name="cart_update"),
    path("checkout/", views.checkout, name="checkout"),
    path("account/", views.account, name="account"),
    path("account/signup/", views.signup, name="signup"),
    path("account/login/", auth.LoginView.as_view(), name="login"),
    path("account/logout/", auth.LogoutView.as_view(), name="logout"),
    path("orders/<int:pk>/", views.order, name="order"),
    path("payments/robokassa/result/", views.robokassa_result, name="robokassa_result"),
    path("payments/robokassa/success/", views.payment_return, name="payment_success"),
    path("payments/robokassa/fail/", views.payment_return, name="payment_fail"),
    path("admin/", admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
