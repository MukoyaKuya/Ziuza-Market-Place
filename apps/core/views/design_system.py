from datetime import timedelta

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from django.views.generic import TemplateView


class DesignSystemView(UserPassesTestMixin, TemplateView):
    """Component Showcase Page displaying all Ziuza Design System primitives and cards."""

    template_name = 'pages/design_system.html'
    raise_exception = True

    def test_func(self):
        return settings.DEBUG or (
            self.request.user.is_authenticated and self.request.user.is_staff
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Ziuza Design System & Component Library'
        today = timezone.localdate()
        context['demo_chart_rows'] = [
            {'day': today - timedelta(days=offset), 'orders': orders, 'revenue': orders * 1000}
            for offset, orders in enumerate([1, 0, 3, 2, 5, 1, 4][::-1])
        ]
        return context
