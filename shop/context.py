def store(request):
    return {"cart_count": sum(int(v) for v in request.session.get("cart", {}).values())}
