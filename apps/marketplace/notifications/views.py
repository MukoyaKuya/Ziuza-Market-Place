from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.utils import safe_next_url
from apps.marketplace.notifications.delivery import apply_preference_to_pending
from apps.marketplace.notifications.forms import NotificationPreferenceForm
from apps.marketplace.notifications.models import Notification, NotificationPreference
from apps.marketplace.notifications.services import mark_notification_read


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)[:50]
    return render(
        request,
        'notifications/list.html',
        {
            'notifications': notifications,
            'page_title': 'Notifications',
            'account_section': 'notifications',
        },
    )


@login_required
@require_POST
def mark_read(request, notification_id):
    mark_notification_read(actor=request.user, notification_id=notification_id)
    return redirect(safe_next_url(request, request.POST.get('next'), 'notifications:list'))


@login_required
@require_http_methods(['GET', 'POST'])
def notification_settings(request):
    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = NotificationPreferenceForm(request.POST or None, instance=preference)
    if request.method == 'POST' and form.is_valid():
        preference = form.save()
        apply_preference_to_pending(preference)
        messages.success(request, 'Notification preferences saved.')
        return redirect('notifications:settings')
    return render(request, 'notifications/settings.html', {
        'form': form,
        'page_title': 'Notification settings',
        'account_section': 'notification_settings',
    })


def unread_count_partial(request):
    count = 0
    if request.user.is_authenticated:
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return render(
        request,
        'notifications/partials/unread_count.html',
        {'unread_count': count},
    )

