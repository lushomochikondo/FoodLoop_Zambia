from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.checks import Error, register

@register()
def configuration_checks(app_configs, **kwargs):
    errors = []
    if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
        errors.append(Error('Choose EMAIL_USE_TLS or EMAIL_USE_SSL, not both.', id='core.E005'))
    for name in ['MEAL_WEIGHT_KG', 'CO2E_KG_PER_KG']:
        value = getattr(settings, name, '')
        if name == 'CO2E_KG_PER_KG' and not value: continue
        try:
            amount = Decimal(value)
            valid = amount.is_finite() and amount > 0
        except (InvalidOperation, TypeError): valid = False
        if not valid: errors.append(Error(f'{name} must be a finite positive number.', id='core.E001'))
    if settings.REQUEST_EXPIRY_HOURS <= 0: errors.append(Error('REQUEST_EXPIRY_HOURS must be positive.', id='core.E002'))
    if settings.CO2E_KG_PER_KG and not settings.CO2E_SOURCE: errors.append(Error('CO2E_SOURCE is required when an emission factor is configured.', id='core.E003'))
    weights = settings.MATCH_WEIGHTS
    if any(not isinstance(v, (int, float)) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        errors.append(Error('Matching weights must be nonnegative with a positive total.', id='core.E004'))
    return errors
