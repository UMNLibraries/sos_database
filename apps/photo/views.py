from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .models import Photo, STATUS_CHOICES


@login_required(login_url="/admin/login/")
def index(request):

    status_lookup = {s[0]: s[1] for s in STATUS_CHOICES}

    status_counts = Photo.objects.all().values("status").annotate(status_count=Count("id")).order_by('-status_count')
    status_counts = [{
        'status_code': item['status'],
        'status_long': status_lookup[item['status']],
        'status_count': item['status_count']
    } for item in list(status_counts)]
    print(status_counts)
    context = {'status_counts': status_counts}

    return render(request, "index.html", context)