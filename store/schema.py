from decimal import Decimal

import graphene
from django.db import transaction
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from .forms import CheckoutForm
from .models import Category, Order, OrderItem, Product


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "sort_order")


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "stock", "image_url", "category")


class CartItemType(graphene.ObjectType):
    product = graphene.Field(ProductType, required=True)
    quantity = graphene.Int(required=True)
    subtotal = graphene.Decimal(required=True)


class CartType(graphene.ObjectType):
    items = graphene.List(graphene.NonNull(CartItemType), required=True)
    total = graphene.Decimal(required=True)
    item_count = graphene.Int(required=True)


class OrderReceiptType(graphene.ObjectType):
    id = graphene.Int(required=True)
    total = graphene.Decimal(required=True)
    status = graphene.String(required=True)


def _session_cart(request):
    raw_cart = request.session.get("cart", {})
    if not isinstance(raw_cart, dict):
        raw_cart = {}

    cart = {}
    for product_id, quantity in raw_cart.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if product_id > 0 and 1 <= quantity <= 99:
            cart[str(product_id)] = quantity

    if cart != raw_cart:
        request.session["cart"] = cart
        request.session.modified = True
    return cart


def _cart_data(request):
    cart = _session_cart(request)
    product_ids = [int(product_id) for product_id in cart]
    products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=product_ids,
            active=True,
            category__active=True,
            stock__gt=0,
        ).select_related("category")
    }

    items = []
    valid_cart = {}
    total = Decimal("0.00")
    item_count = 0
    for product_id, requested_quantity in cart.items():
        product = products.get(int(product_id))
        if product is None:
            continue

        quantity = min(requested_quantity, product.stock)
        valid_cart[product_id] = quantity
        subtotal = product.price * quantity
        total += subtotal
        item_count += quantity
        items.append(
            {"product": product, "quantity": quantity, "subtotal": subtotal}
        )

    if valid_cart != cart:
        request.session["cart"] = valid_cart
        request.session.modified = True

    return {"items": items, "total": total, "item_count": item_count}


def _public_products():
    return Product.objects.filter(
        active=True,
        category__active=True,
    ).select_related("category")


class Query(graphene.ObjectType):
    categories = graphene.List(graphene.NonNull(CategoryType))
    products = graphene.List(
        graphene.NonNull(ProductType),
        search=graphene.String(),
        category_slug=graphene.String(),
    )
    product = graphene.Field(ProductType, id=graphene.Int(required=True))
    cart = graphene.Field(CartType, required=True)

    def resolve_categories(root, info):
        return Category.objects.filter(active=True)

    def resolve_products(root, info, search=None, category_slug=None):
        products = _public_products()
        if search:
            products = products.filter(
                name__icontains=search
            ) | products.filter(brand__icontains=search) | products.filter(
                description__icontains=search
            )
        if category_slug:
            products = products.filter(category__slug=category_slug)
        return products.distinct()

    def resolve_product(root, info, id):
        return _public_products().filter(pk=id).first()

    def resolve_cart(root, info):
        return _cart_data(info.context)


class AddToCart(graphene.Mutation):
    class Arguments:
        product_id = graphene.Int(required=True)
        quantity = graphene.Int(default_value=1)

    cart = graphene.Field(CartType, required=True)
    message = graphene.String(required=True)

    @staticmethod
    def mutate(root, info, product_id, quantity=1):
        if quantity < 1 or quantity > 99:
            raise GraphQLError("La cantidad debe estar entre 1 y 99.")

        product = _public_products().filter(pk=product_id).first()
        if product is None:
            raise GraphQLError("El producto no está disponible.")

        cart = _session_cart(info.context)
        key = str(product.pk)
        new_quantity = cart.get(key, 0) + quantity
        if new_quantity > product.stock:
            raise GraphQLError(
                f"Solo hay {product.stock} unidades disponibles de {product.name}."
            )

        cart[key] = new_quantity
        info.context.session["cart"] = cart
        info.context.session.modified = True
        return AddToCart(
            cart=_cart_data(info.context),
            message="Producto agregado al carrito.",
        )


class UpdateCart(graphene.Mutation):
    class Arguments:
        product_id = graphene.Int(required=True)
        quantity = graphene.Int(required=True)

    cart = graphene.Field(CartType, required=True)
    message = graphene.String(required=True)

    @staticmethod
    def mutate(root, info, product_id, quantity):
        if quantity < 1 or quantity > 99:
            raise GraphQLError("La cantidad debe estar entre 1 y 99.")

        product = _public_products().filter(pk=product_id).first()
        if product is None:
            raise GraphQLError("El producto no está disponible.")
        if quantity > product.stock:
            raise GraphQLError(
                f"Solo hay {product.stock} unidades disponibles de {product.name}."
            )

        cart = _session_cart(info.context)
        key = str(product.pk)
        if key not in cart:
            raise GraphQLError("El producto no está en el carrito.")

        cart[key] = quantity
        info.context.session["cart"] = cart
        info.context.session.modified = True
        return UpdateCart(cart=_cart_data(info.context), message="Carrito actualizado.")


class RemoveFromCart(graphene.Mutation):
    class Arguments:
        product_id = graphene.Int(required=True)

    cart = graphene.Field(CartType, required=True)
    message = graphene.String(required=True)

    @staticmethod
    def mutate(root, info, product_id):
        cart = _session_cart(info.context)
        cart.pop(str(product_id), None)
        info.context.session["cart"] = cart
        info.context.session.modified = True
        return RemoveFromCart(cart=_cart_data(info.context), message="Producto quitado.")


class CreateOrder(graphene.Mutation):
    class Arguments:
        full_name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String(required=True)
        address = graphene.String(required=True)
        payment_method = graphene.String(required=True)
        delivery_notes = graphene.String()

    order = graphene.Field(OrderReceiptType, required=True)
    message = graphene.String(required=True)

    @staticmethod
    def mutate(
        root,
        info,
        full_name,
        email,
        phone,
        address,
        payment_method,
        delivery_notes="",
    ):
        form = CheckoutForm(
            {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "address": address,
                "payment_method": payment_method,
                "delivery_notes": delivery_notes,
            }
        )
        if not form.is_valid():
            errors = "; ".join(
                f"{field}: {', '.join(messages)}"
                for field, messages in form.errors.items()
            )
            raise GraphQLError(f"Los datos del checkout no son válidos: {errors}")

        cart = _session_cart(info.context)
        if not cart:
            raise GraphQLError("El carrito está vacío.")

        quantities = {int(product_id): quantity for product_id, quantity in cart.items()}
        with transaction.atomic():
            products = {
                product.pk: product
                for product in Product.objects.select_for_update()
                .filter(
                    pk__in=quantities,
                    active=True,
                    category__active=True,
                )
                .select_related("category")
            }
            if products.keys() != quantities.keys():
                raise GraphQLError(
                    "Uno o más productos dejaron de estar disponibles."
                )

            for product_id, quantity in quantities.items():
                product = products[product_id]
                if quantity > product.stock:
                    raise GraphQLError(
                        f"Stock insuficiente para {product.name}; "
                        f"quedan {product.stock} unidades."
                    )

            total = sum(
                (
                    products[product_id].price * quantity
                    for product_id, quantity in quantities.items()
                ),
                Decimal("0.00"),
            )
            order_data = form.cleaned_data
            user = info.context.user
            order = Order.objects.create(
                user=user if user.is_authenticated else None,
                total=total,
                **order_data,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=products[product_id],
                        product_name=products[product_id].name,
                        unit_price=products[product_id].price,
                        quantity=quantity,
                    )
                    for product_id, quantity in quantities.items()
                ]
            )
            for product_id, quantity in quantities.items():
                product = products[product_id]
                product.stock -= quantity
                product.save(update_fields=["stock"])

        info.context.session["cart"] = {}
        info.context.session.modified = True
        return CreateOrder(order=order, message="Pedido creado correctamente.")


class Mutation(graphene.ObjectType):
    add_to_cart = AddToCart.Field()
    update_cart = UpdateCart.Field()
    remove_from_cart = RemoveFromCart.Field()
    create_order = CreateOrder.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
