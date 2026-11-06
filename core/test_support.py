from decimal import Decimal

from .services import change_request, handover_code_for


def transition_request(user, request, action):
    """Drive the collection flow as the app now requires, including handover proof."""
    if action == 'confirm' and user.membership.organisation_id == request.listing.provider_id:
        weight = request.quantity if request.listing.unit == 'kg' else Decimal('1.00')
        return change_request(
            user,
            request.pk,
            action,
            code=handover_code_for(request),
            confirmed_quantity=request.quantity,
            confirmed_weight_kg=weight,
        )
    return change_request(user, request.pk, action)
