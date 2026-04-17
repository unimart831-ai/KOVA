from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("add/", views.product_add, name="add"),
    path("import/", views.product_import, name="import"),
    path("categories/", views.category_list, name="categories"),
    path("categories/add/", views.category_add, name="category_add"),
    path("<uuid:product_id>/", views.product_detail, name="detail"),
    path("<uuid:product_id>/edit/", views.product_edit, name="edit"),
    path("<uuid:product_id>/delete/", views.product_delete, name="delete"),
    path("<uuid:product_id>/stock/", views.product_update_stock, name="update_stock"),
    path("<uuid:product_id>/promote/", views.promote_product, name="promote"),
    # Snap to Sell
    path("snap/", views.snap_to_sell, name="snap"),
    path("snap/launch/", views.snap_launch, name="snap_launch"),
]
