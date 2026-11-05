from datetime import timedelta
from decimal import Decimal
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone


def visual_context(requests, pathways):
    today = timezone.localdate()
    start = today - timedelta(days=today.weekday() + 77)
    completed = requests.filter(status='collected', collected_at__date__gte=start,
                                collected_at__date__lte=today)
    rows = completed.annotate(day=TruncDate('collected_at')).values('day').annotate(total=Count('pk'))
    counts = {row['day']: row['total'] for row in rows}
    peak = max(counts.values(), default=0)
    weeks = []
    for week in range(12):
        cells = []
        for weekday in range(7):
            date = start + timedelta(days=week * 7 + weekday)
            count = counts.get(date, 0)
            cells.append({'date': date, 'count': count, 'future': date > today,
                          'level': min(4, max(1, (count * 4 + peak - 1) // peak)) if count and peak else 0})
        weeks.append({'days': cells, 'label': cells[0]['date'].strftime('%d %b')})
    total = sum(Decimal(str(p['kg'])) for p in pathways)
    offset = Decimal(0)
    stops = []
    for item, color in zip(pathways, ['#1F5E3B', '#E1A91B', '#8A5A3C']):
        end = offset + Decimal(str(item['kg'])) / total * 100 if total else offset
        stops.append(f'{color} {offset:.3f}% {end:.3f}%')
        offset = end
    return {'heatmap_weeks': weeks, 'heatmap_total': sum(counts.values()),
            'heatmap_active_days': len(counts), 'heatmap_peak': peak,
            'heatmap_start': start, 'heatmap_end': today,
            'recovery_gradient': ','.join(stops) if total else '#e7eee9 0% 100%',
            'has_recovery': bool(total)}
