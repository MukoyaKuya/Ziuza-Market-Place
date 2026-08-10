from apps.marketplace.categories.models import Category


def nav_categories(request):
    """Context processor providing visible root categories to templates."""
    categories = Category.objects.filter(
        parent=None,
        is_visible=True,
    ).order_by('position', 'name')
    return {
        'nav_categories': categories,
    }
