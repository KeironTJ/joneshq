from app.main import bp
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db, socketio, limiter
from datetime import datetime, timedelta, date, timezone
from app.models import (
    User, Message, MealPlan, ActivityPlan,
    Chore, Achievement, PointsLedger, FamilyMembers, HealthLog,
    TodoList, TodoItem, ContactMessage
)
from app.main.forms import EditProfileForm, ContactForm
from collections import defaultdict
from sqlalchemy import func
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

    # --- Rewards data ---
    family = current_user.get_active_family()
    my_points = 0
    pending_chores = []
    leaderboard = []
    recent_achievements = []
    if family:
        my_points = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).filter_by(user_id=current_user.id, family_id=family.id).scalar()

        pending_chores = Chore.query.filter(
            Chore.family_id == family.id,
            Chore.status == 'pending',
            (Chore.assigned_to == current_user.id) | (Chore.assigned_to == None)
        ).order_by(Chore.due_date.asc().nullslast()).limit(4).all()

        recent_achievements = Achievement.query.filter_by(
            family_id=family.id
        ).order_by(Achievement.date_earned.desc()).limit(3).all()

        member_ids = [fm.user_id for fm in FamilyMembers.query.filter_by(family_id=family.id).all()]
        for uid in member_ids:
            u = User.query.get(uid)
            if u:
                pts = db.session.query(
                    func.coalesce(func.sum(PointsLedger.points), 0)
                ).filter_by(user_id=uid, family_id=family.id).scalar()
                leaderboard.append({'username': u.username, 'points': pts})
        leaderboard.sort(key=lambda x: x['points'], reverse=True)
        leaderboard = leaderboard[:5]

    # --- Health data ---
    health_icon = {'weight': 'fa-weight-scale', 'exercise': 'fa-person-running',
                   'water': 'fa-droplet', 'sleep': 'fa-bed', 'mood': 'fa-face-smile'}
    health_color = {'weight': '#E07A5F', 'exercise': '#4CAF82',
                    'water': '#5B8DEF', 'sleep': '#9B6DD7', 'mood': '#E8A44A'}
    health_unit = {'weight': 'kg', 'exercise': 'min', 'water': 'L', 'sleep': 'hrs', 'mood': '/5'}
    health_summaries = {}
    for cat in ['weight', 'exercise', 'water', 'sleep', 'mood']:
        latest = HealthLog.query.filter_by(
            user_id=current_user.id, category=cat
        ).order_by(HealthLog.date.desc()).first()
        if latest:
            prev = HealthLog.query.filter(
                HealthLog.user_id == current_user.id,
                HealthLog.category == cat,
                HealthLog.date < latest.date
            ).order_by(HealthLog.date.desc()).first()
            trend = None
            if prev:
                diff = latest.value - prev.value
                trend = 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
            health_summaries[cat] = {
                'value': latest.value, 'unit': health_unit[cat],
                'date': latest.date.strftime('%d %b'), 'trend': trend,
                'icon': health_icon[cat], 'color': health_color[cat]
            }

    return render_template('main/dashboard.html',
                           upcoming_meals=upcoming_meals,
                           upcoming_activities=upcoming_activities,
                           recent_messages=recent_messages,
                           my_points=my_points,
                           pending_chores=pending_chores,
                           leaderboard=leaderboard,
                           recent_achievements=recent_achievements,
                           health_summaries=health_summaries,
                           health_icon=health_icon,
                           health_color=health_color)


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

    # --- To-Do items with due dates ---
    from sqlalchemy import or_, and_
    family = current_user.get_active_family()
    list_conditions = [TodoList.user_id == current_user.id]
    if family:
        list_conditions.append(
            and_(TodoList.family_id == family.id, TodoList.family_id.isnot(None))
        )
    my_lists = TodoList.query.filter(or_(*list_conditions)).all()
    list_ids = [l.id for l in my_lists]
    list_map = {l.id: l for l in my_lists}

    todo_items = []
    if list_ids:
        todo_items = TodoItem.query.filter(
            TodoItem.list_id.in_(list_ids),
            TodoItem.due_date >= first_day,
            TodoItem.due_date <= last_day,
        ).all()

    todos_by_day = defaultdict(list)
    for item in todo_items:
        todos_by_day[item.due_date].append(item)

    return render_template('main/calendar.html',
                           title='Family Calendar',
                           month_days=month_days,
                           meals_by_day=meals_by_day,
                           activities_by_day=activities_by_day,
                           todos_by_day=todos_by_day,
                           list_map=list_map,
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


@bp.route('/help', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"], error_message="Too many messages sent. Please try again later.")
def help_and_contact():
    form = ContactForm()
    submitted = False
    if form.validate_on_submit():
        msg = ContactMessage(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            subject=form.subject.data.strip(),
            message=form.message.data.strip(),
        )
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent! We\'ll get back to you soon.', 'success')
        submitted = True
        form = ContactForm(formdata=None)
    return render_template('main/help_contact.html',
                           title='Help & Contact',
                           form=form,
                           submitted=submitted)






