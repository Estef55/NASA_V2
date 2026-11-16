from datetime import datetime, timezone
import os

BASELINE_MIN_SAMPLES = 3
DEVIATION_THRESHOLD = float(os.getenv('LATIRA_BASELINE_RELATIVE_DEVIATION', '0.20'))


def calculate_baseline(connection, astronaut_id, demo=False, before_metric_id=None):
    """Return a per-owner arithmetic baseline; demo and real records never mix."""
    if before_metric_id is not None and not demo:
        rows = connection.execute(
            'SELECT sleep,heart_rate,fatigue,mood FROM metrics WHERE astronaut_id=? AND demo=0 AND id<? ORDER BY id',
            (astronaut_id, before_metric_id),
        ).fetchall()
    else:
        rows = connection.execute(
            'SELECT sleep,heart_rate,fatigue,mood FROM metrics WHERE astronaut_id=? AND demo=? ORDER BY id',
            (astronaut_id, int(demo)),
        ).fetchall()
    if demo:
        rows = rows[:3]
    metrics = ('sleep', 'heart_rate', 'fatigue', 'mood')
    counts = {key: sum(row[key] is not None for row in rows) for key in metrics}
    metric_sufficiency = {key: count >= BASELINE_MIN_SAMPLES for key, count in counts.items()}
    means = {key: sum(float(row[key]) for row in rows if row[key] is not None) / counts[key]
             for key in metrics if metric_sufficiency[key]}
    available_count = sum(count > 0 for count in counts.values())
    sufficient_count = sum(metric_sufficiency.values())
    complete = available_count > 0 and sufficient_count == available_count
    return {
        'astronaut_id': astronaut_id,
        'sample_count': len(rows),
        'minimum_samples': BASELINE_MIN_SAMPLES,
        'sufficient': sufficient_count > 0,
        'fully_sufficient': complete,
        'sufficient_indicator_count': sufficient_count,
        'available_indicator_count': available_count,
        'metric_samples': counts,
        'metric_sufficiency': metric_sufficiency,
        'confidence': 'sufficient' if complete else ('partial' if sufficient_count else 'insufficient'),
        'method': 'per-indicator relative deviation from arithmetic-mean baseline',
        'relative_deviation_threshold': DEVIATION_THRESHOLD,
        'values': means,
    }


def create_deviation_alert(connection, metric_id):
    row = connection.execute('SELECT * FROM metrics WHERE id=?', (metric_id,)).fetchone()
    if not row:
        return
    is_demo = bool(row['demo'])
    if is_demo:
        baseline = calculate_baseline(connection, row['astronaut_id'], True)
        if not baseline['sufficient'] or (row['day'] is not None and row['day'] <= 3):
            return
    else:
        baseline = calculate_baseline(connection, row['astronaut_id'], False, before_metric_id=metric_id)
        if not baseline['sufficient']:
            return
    changes = []
    for key, base in baseline['values'].items():
        value = float(row[key]) if row[key] is not None else None
        if value is not None and base != 0 and abs(value - base) / abs(base) >= DEVIATION_THRESHOLD:
            changes.append(f'{key} {value:g} vs baseline {base:.2f} ({(value-base)/abs(base):+.0%})')
    if changes:
        reason = 'Fictional demo deviation: ' + '; '.join(changes) + f'; relative threshold {DEVIATION_THRESHOLD:.0%}. Not a diagnosis.' if is_demo else 'Personal baseline deviation: ' + '; '.join(changes) + f'; relative threshold {DEVIATION_THRESHOLD:.0%}. This is not a diagnosis.'
        connection.execute(
            'INSERT OR IGNORE INTO alerts(astronaut_id,metric_id,created_at,priority,reason,demo) VALUES(?,?,?,?,?,?)',
            (row['astronaut_id'], metric_id, datetime.now(timezone.utc).isoformat(), 'review', reason, int(is_demo)),
        )
