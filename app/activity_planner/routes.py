from app.activity_planner import bp
from flask import render_template, request, redirect, url_for, flash
from app.models import ActivityPlan, FamilyMembers
from app.activity_planner.forms import AddActivityForm
from flask_login import login_required, current_user
from app import db
from app.decorators import active_family_required
from datetime import datetime, timedelta, date
from collections import defaultdict
import calendar as cal_module


## Family Activity Planner Routes
@bp.route('/activityplanner', methods=['GET', 'POST'])
@login_required
@active_family_required
def activityplanner():
    view = request.args.get('view', 'week')
    today = date.today()

    # Get the family IDs the current user belongs to
    family_ids = [family.id for family in current_user.families]
    family_user_ids = db.session.query(FamilyMembers.user_id).filter(
        FamilyMembers.family_id.in_(family_ids)
    )

    addactivityform = AddActivityForm()

    if view == 'month':
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

        activities = ActivityPlan.query.filter(
            ActivityPlan.user_id.in_(family_user_ids),
            ActivityPlan.activity_start_date <= datetime.combine(last_day, datetime.max.time()),
            ActivityPlan.activity_end_date >= datetime.combine(first_day, datetime.min.time())
        ).order_by(ActivityPlan.activity_start_date.asc(),
                    ActivityPlan.activity_start_time.asc()).all()

        activities_by_day = defaultdict(list)
        for activity in activities:
            start = activity.activity_start_date.date() if isinstance(activity.activity_start_date, datetime) else activity.activity_start_date
            end = activity.activity_end_date.date() if isinstance(activity.activity_end_date, datetime) else activity.activity_end_date
            d = max(start, first_day)
            end_d = min(end, last_day)
            while d <= end_d:
                activities_by_day[d].append(activity)
                d += timedelta(days=1)

        if addactivityform.validate_on_submit():
            activity = ActivityPlan(
                user_id=current_user.id,
                activity_start_date=addactivityform.activity_start_date.data,
                activity_end_date=addactivityform.activity_end_date.data,
                activity_start_time=addactivityform.activity_start_time.data,
                activity_end_time=addactivityform.activity_end_time.data,
                activity_all_day_event=addactivityform.activity_all_day_event.data,
                activity_title=addactivityform.activity_title.data,
                activity_description=addactivityform.activity_description.data,
                activity_comments=addactivityform.activity_comments.data,
                activity_location=addactivityform.activity_location.data
            )
            db.session.add(activity)
            db.session.commit()
            flash('Activity added successfully!', 'success')
            return redirect(url_for('activity_planner.activityplanner', view='month', month=month_offset))

        return render_template('activity_planner/activityplanner.html',
                               title='Activity Planner',
                               view=view,
                               month_days=month_days,
                               activities_by_day=activities_by_day,
                               today=today,
                               target_year=target_year,
                               target_month=target_month,
                               month_offset=month_offset,
                               addactivityform=addactivityform)
    else:
        # Week view
        week_offset = request.args.get('week', 0, type=int)
        start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)

        week_days = [start_of_week + timedelta(days=i) for i in range(7)]

        activities = ActivityPlan.query.filter(
            ActivityPlan.user_id.in_(family_user_ids),
            ActivityPlan.activity_start_date <= datetime.combine(end_of_week, datetime.max.time()),
            ActivityPlan.activity_end_date >= datetime.combine(start_of_week, datetime.min.time())
        ).order_by(ActivityPlan.activity_start_date.asc(),
                    ActivityPlan.activity_start_time.asc()).all()

        activities_by_day = defaultdict(list)
        for activity in activities:
            start = activity.activity_start_date.date() if isinstance(activity.activity_start_date, datetime) else activity.activity_start_date
            end = activity.activity_end_date.date() if isinstance(activity.activity_end_date, datetime) else activity.activity_end_date
            d = max(start, start_of_week)
            end_d = min(end, end_of_week)
            while d <= end_d:
                activities_by_day[d].append(activity)
                d += timedelta(days=1)

        if addactivityform.validate_on_submit():
            activity = ActivityPlan(
                user_id=current_user.id,
                activity_start_date=addactivityform.activity_start_date.data,
                activity_end_date=addactivityform.activity_end_date.data,
                activity_start_time=addactivityform.activity_start_time.data,
                activity_end_time=addactivityform.activity_end_time.data,
                activity_all_day_event=addactivityform.activity_all_day_event.data,
                activity_title=addactivityform.activity_title.data,
                activity_description=addactivityform.activity_description.data,
                activity_comments=addactivityform.activity_comments.data,
                activity_location=addactivityform.activity_location.data
            )
            db.session.add(activity)
            db.session.commit()
            flash('Activity added successfully!', 'success')
            return redirect(url_for('activity_planner.activityplanner', week=week_offset))

        return render_template('activity_planner/activityplanner.html',
                               title='Activity Planner',
                               view=view,
                               week_days=week_days,
                               activities_by_day=activities_by_day,
                               today=today,
                               week_offset=week_offset,
                               addactivityform=addactivityform)


@bp.route('/activity_details/<int:id>', methods=['GET', 'POST'])
@login_required
@active_family_required
def activity_details(id):

    activity = ActivityPlan.query.get_or_404(id)
    editactivityform = AddActivityForm(obj=activity)

    if editactivityform.validate_on_submit():
        editactivityform.populate_obj(activity)
        db.session.commit()
        flash("Activity updated successfully!", "success")
        return redirect(url_for('activity_planner.activity_details', id=activity.id))
    
    return render_template("activity_planner/activity_details.html", 
                           editactivityform=editactivityform, 
                           activity=activity)


@bp.route('/delete_activity/<int:id>', methods=['GET', 'POST'])
@login_required
@active_family_required
def delete_activity(id):
    activity = ActivityPlan.query.get_or_404(id)
    db.session.delete(activity)
    db.session.commit()
    flash("Activity deleted successfully!", "danger")
    return redirect(url_for('activity_planner.activityplanner'))