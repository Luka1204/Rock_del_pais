from .models import SavedCart


MAX_CART_QUANTITY = 99


def normalize_cart(raw_cart):
    if not isinstance(raw_cart, dict):
        return {}

    cart = {}
    for product_id, quantity in raw_cart.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if product_id > 0 and quantity > 0:
            key = str(product_id)
            cart[key] = min(
                cart.get(key, 0) + quantity,
                MAX_CART_QUANTITY,
            )
    return cart


def merge_carts(*carts):
    merged = {}
    for raw_cart in carts:
        for product_id, quantity in normalize_cart(raw_cart).items():
            merged[product_id] = min(
                merged.get(product_id, 0) + quantity,
                MAX_CART_QUANTITY,
            )
    return merged


def save_cart_for_user(user, cart):
    if not user.is_authenticated:
        return

    items = normalize_cart(cart)
    if items:
        SavedCart.objects.update_or_create(
            user_id=user.pk,
            defaults={"items": items},
        )
    else:
        SavedCart.objects.filter(user_id=user.pk).delete()


def restore_cart_for_user(user, session):
    saved_cart = SavedCart.objects.filter(user_id=user.pk).values_list(
        "items", flat=True
    ).first()
    cart = merge_carts(saved_cart, session.get("cart", {}))
    session["cart"] = cart
    session.modified = True
    save_cart_for_user(user, cart)
