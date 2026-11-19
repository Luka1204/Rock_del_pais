def cart_summary(request):
    cart = request.session.get("cart", {})
    try:
        count = sum(max(0, int(quantity)) for quantity in cart.values())
    except (AttributeError, TypeError, ValueError):
        count = 0
    return {"cart_item_count": count}