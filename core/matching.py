from django.conf import settings
from django.utils import timezone

def rank_listing(listing, org):
    """Recommend listings matching the main recovery interest; this does not restrict requests."""
    if not listing.available or listing.pathway != org.pathway or (org.pathway == 'human' and listing.condition == 'spoiled'):
        return None
    same = listing.area.casefold() == org.area.casefold()
    nearby = listing.area.casefold() in {a.casefold() for area, areas in settings.NEARBY_AREAS.items() if area.casefold() == org.area.casefold() for a in areas}
    hours = max(0, (listing.deadline - timezone.now()).total_seconds() / 3600)
    location = 1 if same else (0.6 if nearby else 0.1)
    urgency = max(0, 1 - hours / 48)
    comparable = listing.unit == org.usual_unit
    quantity = min(float(listing.remaining / org.usual_quantity), float(org.usual_quantity / listing.remaining)) if comparable and org.usual_quantity > 0 else 0
    conditions = {'human': {'fresh': 1, 'cooked': 1, 'sealed': 1, 'near_expiry': 0.8, 'damaged': 0.5}, 'feed': {'fresh': 1, 'near_expiry': 0.9, 'spoiled': 0.6}, 'compost': {'spoiled': 1, 'fresh': 0.8}}
    condition = conditions[listing.pathway].get(listing.condition, 0.5)
    from .services import platform_setting
    weights = {
        'location': platform_setting('matching_location_weight', settings.MATCH_WEIGHTS['location'], int),
        'urgency': platform_setting('matching_urgency_weight', settings.MATCH_WEIGHTS['urgency'], int),
        'quantity': platform_setting('matching_quantity_weight', settings.MATCH_WEIGHTS['quantity'], int),
        'condition': platform_setting('matching_condition_weight', settings.MATCH_WEIGHTS['condition'], int),
    }
    weights = {key: max(0, value) for key, value in weights.items()}
    total_weight = sum(weights.values())
    if not total_weight:
        weights = {key: max(0, value) for key, value in settings.MATCH_WEIGHTS.items()}
        total_weight = sum(weights.values()) or 1
    raw = location * weights['location'] + urgency * weights['urgency'] + quantity * weights['quantity'] + condition * weights['condition']
    score = round(100 * raw / total_weight)
    reasons = [('Same area' if same else 'Nearby area' if nearby else listing.area), f'{hours:.0f} hours left', ('Quantity fits your usual need' if comparable and quantity >= .75 else 'Quantity differs from your usual need' if comparable else 'Different unit from your usual need')]
    return score, ' · '.join(reasons)
