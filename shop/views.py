from decimal import Decimal
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Category, Product, Page, Order, OrderItem, Banner, News
from .forms import SignupForm, CheckoutForm
from .payments import payment_url, valid_result


def products():
    return (
        Product.objects.filter(active=True)
        .select_related("category")
        .prefetch_related("images")
    )


def home(request):
    featured = products().filter(featured=True)[:8]
    return render(
        request,
        "shop/home.html",
        {
            "featured": featured,
            "banners": Banner.objects.filter(active=True).select_related("product", "news"),
            "categories": Category.objects.annotate(
                count=Count("products", filter=Q(products__active=True))
            ).order_by("position", "name"),
            "product_count": products().count(),
        },
    )


def category_tree():
    categories = list(Category.objects.annotate(
        count=Count("products", filter=Q(products__active=True))
    ).order_by("position", "name", "pk"))
    children = {}
    for category in categories:
        children.setdefault(category.parent_id, []).append(category)
    result = []

    def visit(category, depth):
        category.depth = depth
        category.tree_children = children.get(category.pk, [])
        category.descendant_ids = [category.pk]
        result.append(category)
        for child in children.get(category.pk, []):
            visit(child, depth + 1)
            category.descendant_ids.extend(child.descendant_ids)
            category.count += child.count

    for root in children.get(None, []):
        visit(root, 0)
    return result


def catalog(request):
    items = products()
    category = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()[:150]
    scale = request.GET.get("scale", "")
    categories = category_tree()
    selected = next((c for c in categories if c.slug == category), None)
    for node in categories:
        node.tree_open = bool(selected and selected.pk in node.descendant_ids)
    if category:
        items = items.filter(category_id__in=selected.descendant_ids if selected else [])
    if q:
        # SQLite's case folding does not cover Cyrillic. Casefold candidate titles for local parity.
        if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            ids = [
                pk
                for pk, title, sku in items.values_list("pk", "title", "sku")
                if q.casefold() in (title + " " + sku).casefold()
            ]
            items = items.filter(pk__in=ids)
        else:
            items = items.filter(Q(title__icontains=q) | Q(sku__icontains=q))
    if scale:
        items = items.filter(scale=scale)
    if request.GET.get("available"):
        items = items.filter(available=True)
    sort = request.GET.get("sort", "title")
    items = items.order_by(
        {"price": "price", "-price": "-price", "title": "title"}.get(sort, "title"),
        "pk",
    )
    page = Paginator(items, 24).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    category_query = query.copy()
    category_query.pop("category", None)
    return render(
        request,
        "shop/catalog.html",
        {
            "page_obj": page,
            "categories": categories,
            "category_roots": [c for c in categories if c.parent_id is None],
            "scales": Product.objects.exclude(scale="")
            .values_list("scale", flat=True)
            .distinct()
            .order_by("scale"),
            "query": query.urlencode(),
            "category_query": category_query.urlencode(),
            "q": q,
            "selected_category": category,
            "selected_scale": scale,
            "sort": sort,
        },
    )


def news_list(request):
    entries = News.objects.filter(published=True, published_at__lte=timezone.now())
    return render(request, "shop/news_list.html", {"page_obj": Paginator(entries, 12).get_page(request.GET.get("page"))})


def news_detail(request, slug):
    entry = get_object_or_404(News, slug=slug, published=True, published_at__lte=timezone.now())
    return render(request, "shop/news_detail.html", {"entry": entry})


def product(request, slug):
    item = get_object_or_404(products(), slug=slug)
    return render(
        request,
        "shop/product.html",
        {
            "product": item,
            "related": products()
            .filter(category=item.category)
            .exclude(pk=item.pk)[:4],
        },
    )


def page(request, slug):
    info_page = get_object_or_404(Page, slug=slug)
    context = {"page": info_page}
    if slug == "contacts":
        intro, shop_marker, rest = info_page.body.partition("Интернет-магазин:")
        shop_text, maker_marker, maker_text = rest.partition("Производитель:")
        if shop_marker and maker_marker:
            context["contact_sections"] = {
                "intro": intro.strip(),
                "shop": shop_text.strip(),
                "maker": maker_text.strip(),
            }
    elif slug == "cash":
        intro, order_marker, rest = info_page.body.partition("Шаг 1.")
        order_text, delivery_marker, delivery_text = rest.partition("Отправка Вашего заказа")
        if order_marker and delivery_marker:
            context["delivery_sections"] = {
                "intro": intro.strip(),
                "order": (order_marker + order_text).strip(),
                "delivery": (delivery_marker + delivery_text).strip(),
            }
    return render(request, "shop/page.html", context)


def cart_rows(request):
    cart = request.session.get("cart", {})
    rows = []
    for item in products().filter(pk__in=[int(k) for k in cart if k.isdigit()]):
        qty = max(1, min(99, int(cart[str(item.pk)])))
        rows.append(
            {
                "product": item,
                "quantity": qty,
                "total": (item.price or Decimal("0")) * qty,
            }
        )
    return rows


def cart(request):
    rows = cart_rows(request)
    return render(
        request,
        "shop/cart.html",
        {"rows": rows, "total": sum((r["total"] for r in rows), Decimal("0"))},
    )


@require_POST
def cart_update(request, pk):
    item = get_object_or_404(products(), pk=pk)
    try:
        qty = int(request.POST.get("quantity", "1"))
    except ValueError:
        return HttpResponseBadRequest("Некорректное количество")
    cart = request.session.get("cart", {})
    if request.POST.get("action") == "remove":
        cart.pop(str(pk), None)
    elif item.price and item.available:
        if request.POST.get("action") != "set":
            qty += int(cart.get(str(pk), 0))
        cart[str(pk)] = max(1, min(99, qty))
        messages.success(request, "Корзина обновлена")
    else:
        messages.info(request, "Наличие или цену этого товара нужно уточнить.")
    request.session["cart"] = cart
    return redirect(
        "cart"
        if request.POST.get("action") in ("set", "remove")
        else item.get_absolute_url()
    )


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("account")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def account(request):
    return render(
        request,
        "shop/account.html",
        {"orders": request.user.orders.prefetch_related("items")},
    )


@login_required
def checkout(request):
    rows = cart_rows(request)
    if not rows:
        return redirect("cart")
    if any(not r["product"].available or not r["product"].price for r in rows):
        messages.error(
            request, "Наличие некоторых товаров изменилось. Обновите корзину."
        )
        return redirect("cart")
    token = request.session.setdefault("checkout_key", str(uuid.uuid4()))
    form = CheckoutForm(request.POST or None, initial={"email": request.user.email})
    if request.method == "POST" and form.is_valid():
        if request.POST.get("checkout_key") != token:
            return HttpResponseBadRequest("Обновите страницу оформления заказа")
        with transaction.atomic():
            # Freeze current prices while persisting immutable line snapshots.
            locked = {
                p.pk: p
                for p in Product.objects.select_for_update().filter(
                    pk__in=[r["product"].pk for r in rows]
                )
            }
            if any(
                not locked[r["product"].pk].available
                or not locked[r["product"].pk].active
                or not locked[r["product"].pk].price
                for r in rows
            ):
                messages.error(request, "Наличие изменилось. Проверьте корзину.")
                return redirect("cart")
            values = {key: form.cleaned_data[key] for key in form.Meta.fields}
            values.update(
                user=request.user,
                consent_at=timezone.now(),
                subtotal=sum(
                    (locked[r["product"].pk].price * r["quantity"] for r in rows),
                    Decimal("0"),
                ),
            )
            order, created = Order.objects.get_or_create(
                checkout_key=token, defaults=values
            )
            for row in rows if created else []:
                p = locked[row["product"].pk]
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    title=p.title,
                    sku=p.sku,
                    price=p.price,
                    quantity=row["quantity"],
                )
        request.session["cart"] = {}
        request.session.pop("checkout_key", None)
        return redirect("order", pk=order.pk)
    return render(
        request,
        "shop/checkout.html",
        {
            "form": form,
            "rows": rows,
            "total": sum(r["total"] for r in rows),
            "checkout_key": token,
        },
    )


@login_required
def order(request, pk):
    obj = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=pk, user=request.user
    )
    return render(
        request, "shop/order.html", {"order": obj, "payment_url": payment_url(obj)}
    )


@csrf_exempt
@require_POST
def robokassa_result(request):
    data = request.POST
    if any(len(data.getlist(k)) != 1 for k in data):
        return HttpResponseBadRequest("Duplicate parameters")
    try:
        pk = int(data.get("InvId", ""))
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid invoice")
    with transaction.atomic():
        obj = get_object_or_404(Order.objects.select_for_update(), pk=pk)
        if not valid_result(data, obj):
            return HttpResponseBadRequest("Invalid signature or amount")
        if obj.paid_at is None:
            obj.status = Order.Status.PAID
            obj.paid_at = timezone.now()
            obj.save(update_fields=["status", "paid_at"])
    return HttpResponse(f"OK{obj.pk}", content_type="text/plain")


def payment_return(request):
    messages.info(
        request,
        "Статус оплаты обновляется после подтверждения платёжной системы. Проверьте заказ в кабинете.",
    )
    return redirect("account")
