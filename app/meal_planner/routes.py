from app.meal_planner import bp
from flask import render_template, request, redirect, url_for, flash, jsonify
from app.models import  MealPlan
from app.meal_planner.forms import AddMealForm
from flask_login import login_required, current_user
from app import db
from datetime import datetime, timedelta, date
from app.decorators import active_family_required
from collections import defaultdict
import calendar


## Meal Planner Routes
@bp.route('/mealplanner', methods=['GET', 'POST'])
@login_required
@active_family_required
def mealplanner():
    view = request.args.get('view', 'week')
    today = date.today()

    if view == 'month':
        month_offset = request.args.get('month', 0, type=int)
        # Calculate target month
        target_month = today.month + month_offset
        target_year = today.year
        while target_month > 12:
            target_month -= 12
            target_year += 1
        while target_month < 1:
            target_month += 12
            target_year -= 1

        cal = calendar.Calendar(firstweekday=0)  # Monday start
        month_days = cal.monthdatescalendar(target_year, target_month)

        first_day = month_days[0][0]
        last_day = month_days[-1][-1]

        mealplan = MealPlan.query.filter(
            MealPlan.meal_date >= datetime.combine(first_day, datetime.min.time()),
            MealPlan.meal_date <= datetime.combine(last_day, datetime.max.time())
        ).order_by(MealPlan.meal_date.asc()).all()

        meals_by_day = defaultdict(list)
        for meal in mealplan:
            meal_day = meal.meal_date.date() if isinstance(meal.meal_date, datetime) else meal.meal_date
            meals_by_day[meal_day].append(meal)

        addMealForm = AddMealForm()
        if addMealForm.validate_on_submit():
            meal = MealPlan(
                user_id=current_user.id,
                meal_title=addMealForm.meal_title.data,
                meal_date=addMealForm.meal_date.data,
                meal_description=addMealForm.meal_description.data,
                meal_source=addMealForm.meal_source.data
            )
            db.session.add(meal)
            db.session.commit()
            flash('Meal added successfully!', 'success')
            return redirect(url_for('meal_planner.mealplanner', view='month', month=month_offset))
        elif request.method == 'POST':
            flash('Please fill in all fields.', 'danger')

        return render_template('meal_planner/mealplanner.html',
                               title='Meal Planner',
                               view=view,
                               month_days=month_days,
                               meals_by_day=meals_by_day,
                               today=today,
                               target_year=target_year,
                               target_month=target_month,
                               month_offset=month_offset,
                               addMealForm=addMealForm)
    else:
        # Week view (existing)
        week_offset = request.args.get('week', 0, type=int)
        start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)

        week_days = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            week_days.append(day)

        mealplan = MealPlan.query.filter(
            MealPlan.meal_date >= datetime.combine(start_of_week, datetime.min.time()),
            MealPlan.meal_date <= datetime.combine(end_of_week, datetime.max.time())
        ).order_by(MealPlan.meal_date.asc()).all()

        meals_by_day = defaultdict(list)
        for meal in mealplan:
            meal_day = meal.meal_date.date() if isinstance(meal.meal_date, datetime) else meal.meal_date
            meals_by_day[meal_day].append(meal)

        addMealForm = AddMealForm()
        if addMealForm.validate_on_submit():
            meal = MealPlan(
                user_id=current_user.id,
                meal_title=addMealForm.meal_title.data,
                meal_date=addMealForm.meal_date.data,
                meal_description=addMealForm.meal_description.data,
                meal_source=addMealForm.meal_source.data
            )
            db.session.add(meal)
            db.session.commit()
            flash('Meal added successfully!', 'success')
            return redirect(url_for('meal_planner.mealplanner', week=week_offset))
        elif request.method == 'POST':
            flash('Please fill in all fields.', 'danger')

        return render_template('meal_planner/mealplanner.html',
                               title='Meal Planner',
                               view=view,
                               week_days=week_days,
                               meals_by_day=meals_by_day,
                               today=today,
                               week_offset=week_offset,
                               addMealForm=addMealForm)

@bp.route('/meal_details/<int:meal_id>', methods=['GET', 'POST'])
@login_required
@active_family_required
def meal_details(meal_id):
    meal = MealPlan.query.get_or_404(meal_id)
    editmealform = AddMealForm(obj=meal)

    if editmealform.validate_on_submit():
        editmealform.populate_obj(meal)
        db.session.commit()
        flash("Meal updated successfully!", "success")
        return redirect(url_for('meal_planner.mealplanner'))

    return render_template('meal_planner/meal_details.html', 
                           title='Meal Details',
                           editmealform=editmealform,
                           meal=meal)



@bp.route('/delete_meal/<int:meal_id>', methods=['GET','POST'])
@login_required
def delete_meal(meal_id):
    meal = MealPlan.query.get_or_404(meal_id)
    db.session.delete(meal)
    db.session.commit()
    flash("Meal deleted successfully!", "success")
    return redirect(url_for('meal_planner.mealplanner'))



