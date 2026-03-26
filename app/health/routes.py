from app.health import bp
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import HealthLog, HealthCategory
from app.health.forms import HealthLogForm, HealthCategoryForm
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import func
import re


# Default categories seeded on first visit
DEFAULT_CATEGORIES = [
    {'key': 'weight',      'label': 'Weight',       'unit': 'lbs',   'icon': 'fa-weight-scale',    'color': '#E07A5F', 'aggregation': 'latest', 'daily_goal': None,  'sort_order': 1},
    {'key': 'exercise',    'label': 'Exercise',     'unit': 'min',   'icon': 'fa-person-running',  'color': '#4CAF82', 'aggregation': 'sum',    'daily_goal': 30,    'sort_order': 2},
    {'key': 'water',       'label': 'Water Intake', 'unit': 'L',     'icon': 'fa-droplet',         'color': '#5B8DEF', 'aggregation': 'sum',    'daily_goal': 2.0,   'sort_order': 3},
    {'key': 'sleep',       'label': 'Sleep',        'unit': 'hrs',   'icon': 'fa-bed',             'color': '#9B6DD7', 'aggregation': 'sum',    'daily_goal': 8,     'sort_order': 4},
    {'key': 'mood',        'label': 'Mood',         'unit': '/5',    'icon': 'fa-face-smile',      'color': '#E8A44A', 'aggregation': 'latest', 'daily_goal': None,  'sort_order': 5},
    {'key': 'steps',       'label': 'Steps',        'unit': 'steps', 'icon': 'fa-shoe-prints',     'color': '#00BCD4', 'aggregation': 'sum',    'daily_goal': 10000, 'sort_order': 6},
    {'key': 'screen_time', 'label': 'Screen Time',  'unit': 'hrs',   'icon': 'fa-tv',              'color': '#FF7043', 'aggregation': 'sum',    'daily_goal': None,  'sort_order': 7},
    {'key': 'reading',     'label': 'Reading',      'unit': 'min',   'icon': 'fa-book',            'color': '#8D6E63', 'aggregation': 'sum',    'daily_goal': 30,    'sort_order': 8},
    {'key': 'driving',     'label': 'Driving',      'unit': 'min',   'icon': 'fa-car',             'color': '#78909C', 'aggregation': 'sum',    'daily_goal': None,  'sort_order': 9},
    {'key': 'fruit_veg',   'label': 'Fruit & Veg',  'unit': 'portions', 'icon': 'fa-apple-whole',  'color': '#4CAF82', 'aggregation': 'sum',    'daily_goal': 5,     'sort_order': 10},
    {'key': 'meditation',  'label': 'Meditation',   'unit': 'min',   'icon': 'fa-om',              'color': '#9B6DD7', 'aggregation': 'sum',    'daily_goal': 10,    'sort_order': 11},
    {'key': 'calories',    'label': 'Calories',     'unit': 'kcal',  'icon': 'fa-fire',            'color': '#E25D8B', 'aggregation': 'sum',    'daily_goal': 2000,  'sort_order': 12},
]


def _ensure_categories(user_id):
    """Seed default categories for a user if they have none."""
    existing = HealthCategory.query.filter_by(user_id=user_id).count()
    if existing == 0:
        for cat in DEFAULT_CATEGORIES:
            db.session.add(HealthCategory(user_id=user_id, **cat))
        db.session.commit()


def _get_categories(user_id):
    """Return the user's active health categories ordered by sort_order."""
    return HealthCategory.query.filter_by(
        user_id=user_id, active=True
    ).order_by(HealthCategory.sort_order.asc(), HealthCategory.label.asc()).all()


def _get_category_map(user_id):
    """Return a dict mapping category key -> HealthCategory object."""
    cats = HealthCategory.query.filter_by(user_id=user_id).all()
    return {c.key: c for c in cats}


def _daily_totals(user_id, category_key, aggregation, start_date, end_date):
    """Get daily aggregated values for a category over a date range.

    For 'sum' categories: sums all entries per day.
    For 'latest' categories: takes the last-entered value per day.
    """
    if aggregation == 'sum':
        rows = db.session.query(
            HealthLog.date,
            func.sum(HealthLog.value).label('total')
        ).filter(
            HealthLog.user_id == user_id,
            HealthLog.category == category_key,
            HealthLog.date >= start_date,
            HealthLog.date <= end_date
        ).group_by(HealthLog.date).order_by(HealthLog.date.asc()).all()
        return [(r.date, r.total) for r in rows]
    else:
        # 'latest' — use the most recent entry per day (highest id)
        subq = db.session.query(
            HealthLog.date,
            func.max(HealthLog.id).label('max_id')
        ).filter(
            HealthLog.user_id == user_id,
            HealthLog.category == category_key,
            HealthLog.date >= start_date,
            HealthLog.date <= end_date
        ).group_by(HealthLog.date).subquery()

        rows = db.session.query(HealthLog.date, HealthLog.value).join(
            subq, HealthLog.id == subq.c.max_id
        ).order_by(HealthLog.date.asc()).all()
        return [(r.date, r.value) for r in rows]


def _today_value(user_id, category_key, aggregation):
    """Get the current day's total or latest value."""
    today = date.today()
    totals = _daily_totals(user_id, category_key, aggregation, today, today)
    if totals:
        return totals[0][1]
    return 0


# ========== DASHBOARD ==========

@bp.route('/health', methods=['GET', 'POST'])
@login_required
def health_dashboard():
    _ensure_categories(current_user.id)
    categories = _get_categories(current_user.id)
    cat_map = {c.key: c for c in categories}

    form = HealthLogForm()
    form.category.choices = [(c.key, f"{c.label} ({c.unit})") for c in categories]

    today = date.today()

    if form.validate_on_submit():
        cat = cat_map.get(form.category.data)
        unit = cat.unit if cat else ''
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

    # Last 30 days of raw logs (for the log list)
    thirty_days_ago = today - timedelta(days=30)
    log_query = HealthLog.query.filter(
        HealthLog.user_id == current_user.id,
        HealthLog.date >= thirty_days_ago
    )
    if cat_filter != 'all':
        log_query = log_query.filter_by(category=cat_filter)
    logs = log_query.order_by(HealthLog.date.desc(), HealthLog.created_at.desc()).all()

    # Summary cards with same-day totalling
    summaries = {}
    for cat in categories:
        # Today's aggregated value
        today_val = _today_value(current_user.id, cat.key, cat.aggregation)

        # Latest day with data (for the summary card)
        daily = _daily_totals(current_user.id, cat.key, cat.aggregation,
                              thirty_days_ago, today)
        if daily:
            latest_date, latest_val = daily[-1]
            # Trend: compare last two different days
            trend = None
            if len(daily) >= 2:
                prev_val = daily[-2][1]
                diff = latest_val - prev_val
                trend = 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
            # Goal progress
            goal_pct = None
            if cat.daily_goal and cat.daily_goal > 0:
                goal_pct = min(round(today_val / cat.daily_goal * 100), 100)
            summaries[cat.key] = {
                'value': latest_val,
                'today_value': today_val,
                'unit': cat.unit,
                'date': latest_date.strftime('%d %b') if hasattr(latest_date, 'strftime') else str(latest_date),
                'trend': trend,
                'icon': cat.icon,
                'color': cat.color,
                'daily_goal': cat.daily_goal,
                'goal_pct': goal_pct,
                'aggregation': cat.aggregation,
            }

    # Chart data (daily totals for last 30 days)
    chart_data = {}
    for cat in categories:
        if cat_filter != 'all' and cat.key != cat_filter:
            continue
        daily = _daily_totals(current_user.id, cat.key, cat.aggregation,
                              thirty_days_ago, today)
        if daily:
            chart_data[cat.key] = [
                {'date': d.strftime('%d %b') if hasattr(d, 'strftime') else str(d), 'value': v}
                for d, v in daily
            ]

    return render_template('health/dashboard.html',
                           title='Health Tracker',
                           form=form,
                           logs=logs,
                           categories=categories,
                           summaries=summaries,
                           chart_data=chart_data,
                           cat_filter=cat_filter,
                           cat_map=cat_map,
                           today=today)


# ========== DELETE LOG ==========

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


# ========== CATEGORY SETTINGS ==========

@bp.route('/health/settings', methods=['GET', 'POST'])
@login_required
def health_settings():
    _ensure_categories(current_user.id)
    form = HealthCategoryForm()

    if form.validate_on_submit():
        # Create a new custom category
        key = re.sub(r'[^a-z0-9]+', '_', form.label.data.lower().strip())[:30]
        # Ensure unique key
        existing = HealthCategory.query.filter_by(user_id=current_user.id, key=key).first()
        if existing:
            flash('A category with that name already exists.', 'warning')
            return redirect(url_for('health.health_settings'))
        cat = HealthCategory(
            user_id=current_user.id,
            key=key,
            label=form.label.data.strip(),
            unit=form.unit.data.strip(),
            icon=form.icon.data,
            color=form.color.data,
            aggregation=form.aggregation.data,
            daily_goal=form.daily_goal.data,
            sort_order=form.sort_order.data or 99
        )
        db.session.add(cat)
        db.session.commit()
        flash(f'Category "{cat.label}" created!', 'success')
        return redirect(url_for('health.health_settings'))

    categories = HealthCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(HealthCategory.sort_order.asc(), HealthCategory.label.asc()).all()

    return render_template('health/settings.html',
                           title='Health Settings',
                           form=form,
                           categories=categories)


@bp.route('/health/settings/<int:id>/edit', methods=['POST'])
@login_required
def edit_category(id):
    cat = HealthCategory.query.get_or_404(id)
    if cat.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('health.health_settings'))

    cat.label = request.form.get('label', cat.label).strip()[:64]
    cat.unit = request.form.get('unit', cat.unit).strip()[:20]
    cat.icon = request.form.get('icon', cat.icon)
    cat.color = request.form.get('color', cat.color)
    cat.aggregation = request.form.get('aggregation', cat.aggregation)
    goal = request.form.get('daily_goal', '')
    cat.daily_goal = float(goal) if goal and goal.strip() else None
    sort_val = request.form.get('sort_order', '0')
    cat.sort_order = int(sort_val) if sort_val and sort_val.strip() else 0
    db.session.commit()
    flash(f'Category "{cat.label}" updated.', 'success')
    return redirect(url_for('health.health_settings'))


@bp.route('/health/settings/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_category(id):
    cat = HealthCategory.query.get_or_404(id)
    if cat.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('health.health_settings'))
    cat.active = not cat.active
    db.session.commit()
    status = 'enabled' if cat.active else 'disabled'
    flash(f'Category "{cat.label}" {status}.', 'info')
    return redirect(url_for('health.health_settings'))


@bp.route('/health/settings/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    cat = HealthCategory.query.get_or_404(id)
    if cat.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('health.health_settings'))
    # Delete associated logs
    HealthLog.query.filter_by(user_id=current_user.id, category=cat.key).delete()
    db.session.delete(cat)
    db.session.commit()
    flash(f'Category "{cat.label}" and its logs deleted.', 'danger')
    return redirect(url_for('health.health_settings'))
