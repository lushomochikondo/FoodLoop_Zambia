"""On-demand pilot routing. No coordinates are persisted in application records."""
import math
import requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
import json


def destination_for(listing, user, org):
    if listing.pickup_latitude is None or listing.pickup_longitude is None:
        return None
    exact = bool(user.is_staff or listing.share_pickup_pin or
                 (org and listing.provider_id == org.pk) or
                 (org and listing.requests.filter(recipient=org, status__in=['accepted', 'ready', 'collected']).exists()))
    lat, lon = float(listing.pickup_latitude), float(listing.pickup_longitude)
    return {'latitude': lat if exact else round(lat, 2),
            'longitude': lon if exact else round(lon, 2), 'exact': exact}


@login_required
@never_cache
@require_POST
def collection_route(request, pk):
    from .views import visible
    from .services import organisation
    org = None if request.user.is_staff else organisation(request.user)
    if org and org.status != 'approved':
        return JsonResponse({'error': 'Organisation approval is required for route planning.'}, status=403)
    listing = get_object_or_404(visible(request.user), pk=pk)
    destination = destination_for(listing, request.user, org)
    if not destination:
        return JsonResponse({'error': 'The donor has not added a pickup pin yet.'}, status=409)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        lat, lon = float(data['latitude']), float(data['longitude'])
        mode = data.get('mode', 'driving')
        preference = data.get('preference', 'distance')
        if not all(map(math.isfinite, [lat, lon])) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError
        if mode not in ('driving', 'walking', 'cycling') or preference not in ('distance', 'duration'):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        return JsonResponse({'error': 'Choose a valid starting point and travel mode.'}, status=400)
    # The provider is fixed by configuration, never supplied by the caller.
    if not cache.add('routing-user-' + str(request.user.pk), True, 3):
        return JsonResponse({'error': 'Please wait a few seconds before requesting another route.'}, status=429)
    if not cache.add('routing-provider-slot', True, 1):
        return JsonResponse({'error': 'The route planner is busy. Please try again shortly.'}, status=429)
    profile = {'driving':'car', 'walking':'foot', 'cycling':'bike'}[mode]
    endpoint = settings.ROUTING_BASE_URL.rstrip('/') + f'/routed-{profile}/route/v1/driving/'
    coordinates = f'{lon:.6f},{lat:.6f};{destination["longitude"]:.6f},{destination["latitude"]:.6f}'
    try:
        response = requests.get(endpoint + coordinates,
            params={'overview':'simplified', 'geometries':'geojson', 'steps':'true', 'alternatives':'true'},
            headers={'User-Agent':'FoodLoopZambia/1.0 (pilot; https://foodloop-zambia.onrender.com/contact/)'}, timeout=(4, 10))
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 'Ok' or not result.get('routes'):
            return JsonResponse({'error':'No mapped route was found. Try another starting point or navigation app.'}, status=422)
        routes = []
        for route in result['routes'][:3]:
            routes.append({'distance':route['distance'], 'duration':route['duration'], 'geometry':route['geometry'],
                           'steps':[{'name':step.get('name', ''), 'distance':step['distance'],
                                     'type':step['maneuver']['type'], 'modifier':step['maneuver'].get('modifier', '')}
                                    for leg in route.get('legs', []) for step in leg.get('steps', [])][:200]})
        routes.sort(key=lambda item: item[preference])
        return JsonResponse({'routes': routes, 'destination':destination, 'deadline':listing.deadline.isoformat()})
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError, AttributeError):
        return JsonResponse({'error':'Route estimates are temporarily unavailable. Use the navigation links or try again.'}, status=503)
