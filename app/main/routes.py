from app.main import bp
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db, socketio
from datetime import datetime, timedelta, date, timezone
from app.models import User, Message, MealPlan, ActivityPlan
from app.main.forms import EditProfileForm
from collections import defaultdict
import calendar as cal_module


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():

    return render_template('main/index.html')

@bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    today = datetime.now(timezone.utc).date()

    upcoming_meals = MealPlan.query.filter(
        MealPlan.meal_date >= datetime.combine(today, datetime.min.time())
    ).order_by(MealPlan.meal_date.asc()).limit(3).all()

    upcoming_activities = ActivityPlan.query.filter(
        ActivityPlan.activity_start_date >= datetime.combine(today, datetime.min.time())
    ).order_by(ActivityPlan.activity_start_date.asc()).limit(3).all()

    recent_messages = Message.query.filter_by(deleted=False).order_by(
        Message.timestamp.desc()
    ).limit(5).all()

    return render_template('main/dashboard.html',
                           upcoming_meals=upcoming_meals,
                           upcoming_activities=upcoming_activities,
                           recent_messages=recent_messages)


@bp.route('/calendar')
@login_required
def master_calendar():
    today = date.today()
    month_offset = request.args.get('month', 0, type=int)

    target_month = today.month + month_offset
    target_year = today.year
    while target_month > 12:
        target_month -= 12
        target_year += 1
    while target_month < 1:
        target_month += 12
        target_year -= 1

    cal = cal_module.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(target_year, target_month)

    first_day = month_days[0][0]
    last_day = month_days[-1][-1]

    meals = MealPlan.query.filter(
        MealPlan.meal_date >= datetime.combine(first_day, datetime.min.time()),
        MealPlan.meal_date <= datetime.combine(last_day, datetime.max.time())
    ).order_by(MealPlan.meal_date.asc()).all()

    activities = ActivityPlan.query.filter(
        ActivityPlan.activity_start_date <= datetime.combine(last_day, datetime.max.time()),
        ActivityPlan.activity_end_date >= datetime.combine(first_day, datetime.min.time())
    ).order_by(ActivityPlan.activity_start_date.asc()).all()

    meals_by_day = defaultdict(list)
    for meal in meals:
        d = meal.meal_date.date() if isinstance(meal.meal_date, datetime) else meal.meal_date
        meals_by_day[d].append(meal)

    activities_by_day = defaultdict(list)
    for act in activities:
        start = act.activity_start_date.date() if isinstance(act.activity_start_date, datetime) else act.activity_start_date
        end = act.activity_end_date.date() if isinstance(act.activity_end_date, datetime) else act.activity_end_date
        d = max(start, first_day)
        end_d = min(end, last_day)
        while d <= end_d:
            activities_by_day[d].append(act)
            d += timedelta(days=1)

    return render_template('main/calendar.html',
                           title='Family Calendar',
                           month_days=month_days,
                           meals_by_day=meals_by_day,
                           activities_by_day=activities_by_day,
                           today=today,
                           target_year=target_year,
                           target_month=target_month,
                           month_offset=month_offset)


@bp.route('/user_profile/<username>', methods=['GET', 'POST'])
@login_required
def user_profile(username):

    user = User.query.filter_by(username=username).first()
    form = EditProfileForm(obj=user)

    if form.validate_on_submit():
        form.populate_obj(user)
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('main.user_profile', username=user.username))

    if not user:
        return render_template('main/404.html'), 404

    return render_template('main/user_profile.html', 
                           user=user,
                           form=form)






