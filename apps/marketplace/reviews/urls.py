from django.urls import path

from apps.marketplace.reviews import views

app_name = 'reviews'

urlpatterns = [
    path('account/orders/items/<uuid:order_item_id>/review/', views.create_review_view, name='create'),
    path('account/reviews/<uuid:review_id>/edit/', views.edit_review_view, name='edit'),
    path('account/reviews/media/<uuid:media_id>/delete/', views.delete_media_view, name='delete_media'),
    path('reviews/<uuid:review_id>/helpful/', views.helpful_vote_view, name='helpful_vote'),
    path('reviews/<uuid:review_id>/report/', views.report_review_view, name='report'),
    path('seller/reviews/<uuid:review_id>/respond/', views.seller_response_view, name='seller_response'),
]
