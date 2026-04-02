from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .models import Photo, STATUS_CHOICES
from apps.photo.utils.export import build_park_summary
from apps.park.models import Park


@login_required(login_url="/admin/login/")
def index(request):

    status_lookup = {s[0]: s[1] for s in STATUS_CHOICES}

    status_counts = Photo.objects.all().values("status").annotate(status_count=Count("id")).order_by('-status_count')
    status_counts = [{
        'status_code': item['status'],
        'status_long': status_lookup[item['status']],
        'status_count': item['status_count']
    } for item in list(status_counts)]
    # print(status_counts)

    park_counts = build_park_summary().sort_values(['approved_photos', 'pending_photos', 'total_photos'], ascending=False).to_dict(orient="records")

    context = {'status_counts': status_counts, 'park_counts': park_counts}

    return render(request, "index.html", context)