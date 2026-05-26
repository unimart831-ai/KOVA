from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("add/", views.product_add, name="add"),
    path("import/", views.product_import, name="import"),
    path("alerts/", views.stock_alerts, name="alerts"),
    path("alerts/read-all/", views.stock_alerts_read_all, name="alerts_read_all"),
    path("alerts/<uuid:alert_id>/read/", views.stock_alert_read, name="alert_read"),
    path("categories/", views.category_list, name="categories"),
    path("categories/add/", views.category_add, name="category_add"),
    path("categories/<uuid:category_id>/edit/", views.category_edit, name="category_edit"),
    path("categories/<uuid:category_id>/delete/", views.category_delete, name="category_delete"),
    path("<uuid:product_id>/", views.product_detail, name="detail"),
    path("<uuid:product_id>/snap-status/", views.snap_pipeline_status, name="snap_status"),
    path("<uuid:product_id>/edit/", views.product_edit, name="edit"),
    path("<uuid:product_id>/delete/", views.product_delete, name="delete"),
    path("<uuid:product_id>/stock/", views.product_update_stock, name="update_stock"),
    path("<uuid:product_id>/sale/", views.product_record_sale, name="record_sale"),
    path("<uuid:product_id>/promote/", views.promote_product, name="promote"),
    path("<uuid:product_id>/quick-post/", views.quick_post_product, name="quick_post"),
    path("<uuid:product_id>/reidentify/", views.reidentify_product, name="reidentify"),
    path("<uuid:product_id>/fix-promote/", views.fix_and_promote, name="fix_promote"),
    path("<uuid:product_id>/expand-photos/", views.expand_product_photos_view, name="expand_photos"),
    path("<uuid:product_id>/toggle-primary-image/", views.toggle_primary_image_view, name="toggle_primary_image"),
    # Snap to Sell
    path("snap/", views.snap_to_sell, name="snap"),
    path("snap/launch/", views.snap_launch, name="snap_launch"),
    # Batch Snap
    path("snap/batch/", views.snap_batch, name="snap_batch"),
    path("snap/batch/launch/", views.snap_batch_launch, name="snap_batch_launch"),
    path("snap/batch/transcribe/", views.snap_batch_transcribe, name="snap_batch_transcribe"),
    path("snap/batch/status/", views.batch_snap_pipeline_status, name="batch_snap_status"),
    # Receipt to Restock
    path("restock/", views.restock_scan, name="restock"),
    path("restock/<uuid:scan_id>/status/", views.restock_pipeline_status, name="restock_status"),
    path("restock/<uuid:scan_id>/retry/", views.restock_retry, name="restock_retry"),
    path("restock/<uuid:scan_id>/add-item/", views.restock_add_unmatched, name="restock_add_item"),
]
