from app.health import bp
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import HealthLog
from app.health.forms import HealthLogForm
from datetime import date, timedelta
from collections import defaultdict


UNIT_MAP = {
    'weight': 'lbs',
    'exercise': 'min',
    'water': 'L',
    'sleep': 'hrs',
    'mood': '/5'
}

ICON_MAP = {
    'weight': 'fa-weight-scale',
    'exercise': 'fa-person-running',
    'water': 'fa-droplet',
    'sleep': 'fa-bed',
    'mood': 'fa-face-smile'
}

COLOR_MAP = {
    'weight': '#E07A5F',
    'exercise': '#4CAF82',
    'water': '#5B8DEF',
    'sleep': '#9B6DD7',
    'mood': '#E8A44A'
}


@bp.route('/health', methods=['GET', 'POST'])
@login_required
def health_dashboard():
    form = HealthLogForm()
    today = date.today()

    if form.validate_on_submit():
        unit = UNIT_MAP.get(form.category.data, '')
        log = HealthLog(
            user_id=current_user.id,
            date=form.date.data,
            category=form.category.data,
            value=form.value.data,
            unit=unit,
            notes=form.notes.data
        )
        db.session.add(log)
        db.session.commit()
        flash('Health log saved!', 'success')
        return redirect(url_for('health.health_dashboard'))

    # Category filter
    cat_filter = request.args.get('cat', 'all')

    # Last 30 days of logs
    thirty_days_ago = today - timedelta(days=30)
    query = HealthLog.query.filter(
        HealthLog.user_id == current_user.id,
        HealthLog.date >= thirty_days_ago
    )
    if cat_filter != 'all':
        query = query.filter_by(category=cat_filter)
    logs = query.order_by(HealthLog.date.desc()).all()

    # Chart data (last 30 days for the selected or all categories)
    chart_data = defaultdict(list)
    for log in reversed(logs):
        chart_data[log.category].append({
            'date': log.date.strftime('%d %b'),
            'value': log.value
        })

    # Summary cards: latest value per category
    summaries = {}
    for cat in ['weight', 'exercise', 'water', 'sleep', 'mood']:
        latest = HealthLog.query.filter_by(
            user_id=current_user.id, category=cat
        ).order_by(HealthLog.date.desc()).first()
        if latest:
            # Get trend (compare to previous)
            prev = HealthLog.query.filter(
                HealthLog.user_id == current_user.id,
                HealthLog.category == cat,
                HealthLog.date < latest.date
            ).order_by(HealthLog.date.desc()).first()
            trend = None
            if prev:
                diff = latest.value - prev.value
                trend = 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
            summaries[cat] = {
                'value': latest.value,
                'unit': UNIT_MAP[cat],
                'date': latest.date.strftime('%d %b'),
                'trend': trend,
                'icon': ICON_MAP[cat],
                'color': COLOR_MAP[cat]
            }

    return render_template('health/dashboard.html',
                           title='Health Tracker',
                           form=form,
                           logs=logs,
                           summaries=summaries,
                           chart_data=dict(chart_data),
                           cat_filter=cat_filter,
                           color_map=COLOR_MAP,
                           icon_map=ICON_MAP,
                           unit_map=UNIT_MAP)


@bp.route('/health/<int:id>/delete', methods=['POST'])
@login_required
def delete_log(id):
    log = HealthLog.query.get_or_404(id)
    if log.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('health.health_dashboard'))
    db.session.delete(log)
    db.session.commit()
    flash('Log entry deleted.', 'danger')
    return redirect(url_for('health.health_dashboard'))
