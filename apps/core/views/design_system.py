from datetime import date, timedelta

from django.views.generic import TemplateView


class DesignSystemView(TemplateView):
    """Component Showcase Page displaying all Ziuza Design System primitives and cards."""

    template_name = 'pages/design_system.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Ziuza Design System & Component Library'
        today = date.today()
        context['demo_chart_rows'] = [
            {'day': today - timedelta(days=offset), 'orders': orders, 'revenue': orders * 1000}
            for offset, orders in enumerate([1, 0, 3, 2, 5, 1, 4][::-1])
        ]
        return context
