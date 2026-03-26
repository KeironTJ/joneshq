from app.rewards import bp
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.decorators import active_family_required
from app.models import (
    Chore, Achievement, Reward, RewardRedemption,
    BehaviourEntry, PointsLedger, FamilyMembers, User
)
from app.rewards.forms import ChoreForm, AchievementForm, RewardForm, BehaviourForm
from datetime import datetime, date, timedelta
from collections import defaultdict
from sqlalchemy import func, and_


def _family_members():
    """Return a list of (user_id, username) tuples for the active family."""
    family = current_user.get_active_family()
    if not family:
        return []
    member_ids = [fm.user_id for fm in FamilyMembers.query.filter_by(family_id=family.id).all()]
    users = User.query.filter(User.id.in_(member_ids)).order_by(User.username).all()
    return [(u.id, u.username) for u in users]


def _user_points(user_id, family_id):
    """Return total points for a user in a family."""
    total = db.session.query(func.coalesce(func.sum(PointsLedger.points), 0)).filter_by(
        user_id=user_id, family_id=family_id
    ).scalar()
    return total


def _add_points(user_id, family_id, points, source_type, source_id, description):
    """Add a points ledger entry."""
    entry = PointsLedger(
        family_id=family_id, user_id=user_id, points=points,
        source_type=source_type, source_id=source_id, description=description
    )
    db.session.add(entry)


def _is_parent():
    """Check if the current user is a parent (owner or co-owner) in the active family."""
    family = current_user.get_active_family()
    if not family:
        return False
    fm = FamilyMembers.query.filter_by(user_id=current_user.id, family_id=family.id).first()
    return fm and fm.role_in_family in ('owner', 'co-owner')


def _spawn_next_chore(chore):
    """Create the next occurrence of a recurring chore."""
    if chore.recurring == 'none' or not chore.due_date:
        return
    if chore.recurring == 'daily':
        next_date = chore.due_date + timedelta(days=1)
    elif chore.recurring == 'weekly':
        next_date = chore.due_date + timedelta(weeks=1)
    elif chore.recurring == 'monthly':
        m = chore.due_date.month + 1
        y = chore.due_date.year
        if m > 12:
            m = 1
            y += 1
        day = min(chore.due_date.day, 28)
        next_date = chore.due_date.replace(year=y, month=m, day=day)
    else:
        return

    new_chore = Chore(
        family_id=chore.family_id,
        created_by=chore.created_by,
        assigned_to=chore.assigned_to,
        title=chore.title,
        description=chore.description,
        points=chore.points,
        due_date=next_date,
        recurring=chore.recurring,
        status='pending'
    )
    db.session.add(new_chore)


# ========== REWARDS HUB ==========

@bp.route('/rewards')
@login_required
@active_family_required
def rewards_hub():
    family = current_user.get_active_family()
    members = _family_members()

    pending_chores = Chore.query.filter_by(family_id=family.id, status='pending').order_by(
        Chore.due_date.asc().nullslast(), Chore.created_at.desc()
    ).limit(5).all()

    awaiting_approval = Chore.query.filter_by(family_id=family.id, status='awaiting_approval').count()

    pending_redemptions_query = db.session.query(RewardRedemption).join(Reward).filter(
        Reward.family_id == family.id, RewardRedemption.status == 'pending'
    )
    pending_redemptions = pending_redemptions_query.count()

    # Fetch actual objects for parent approvals widget
    chores_awaiting = []
    redemptions_awaiting = []
    if _is_parent():
        chores_awaiting = Chore.query.filter_by(
            family_id=family.id, status='awaiting_approval'
        ).order_by(Chore.completed_at.desc()).limit(10).all()
        redemptions_awaiting = pending_redemptions_query.order_by(
            RewardRedemption.redeemed_at.desc()
        ).limit(10).all()

    recent_achievements = Achievement.query.filter_by(family_id=family.id).order_by(
        Achievement.date_earned.desc()
    ).limit(5).all()

    available_rewards = Reward.query.filter_by(family_id=family.id, available=True).order_by(
        Reward.points_cost.asc()
    ).all()

    leaderboard = []
    for uid, uname in members:
        pts = _user_points(uid, family.id)
        leaderboard.append({'user_id': uid, 'username': uname, 'points': pts})
    leaderboard.sort(key=lambda x: x['points'], reverse=True)

    my_points = _user_points(current_user.id, family.id)
    is_parent = _is_parent()

    # Child summary cards for parents
    child_summaries = []
    if is_parent:
        children = _child_members(family.id)
        today_date = date.today()
        start_of_week = today_date - timedelta(days=today_date.weekday())
        for child in children:
            pts = _user_points(child.id, family.id)
            week_pts = db.session.query(
                func.coalesce(func.sum(PointsLedger.points), 0)
            ).filter(
                PointsLedger.user_id == child.id,
                PointsLedger.family_id == family.id,
                PointsLedger.created_at >= start_of_week.isoformat()
            ).scalar()
            pending = Chore.query.filter(
                Chore.family_id == family.id,
                Chore.status == 'pending',
                Chore.assigned_to == child.id
            ).count()
            streak = _calculate_streak(child.id, family.id)
            # Behaviour this week
            week_beh = BehaviourEntry.query.filter(
                BehaviourEntry.family_id == family.id,
                BehaviourEntry.user_id == child.id,
                BehaviourEntry.date >= start_of_week,
                BehaviourEntry.date <= today_date
            ).all()
            beh_avg = round(sum(e.rating for e in week_beh) / len(week_beh), 1) if week_beh else None
            child_summaries.append({
                'child': child,
                'total_points': pts,
                'week_points': week_pts,
                'pending_chores': pending,
                'streak': streak,
                'behaviour_avg': beh_avg
            })

    return render_template('rewards/rewards_hub.html',
                           title='Rewards Hub',
                           pending_chores=pending_chores,
                           awaiting_approval=awaiting_approval,
                           pending_redemptions=pending_redemptions,
                           chores_awaiting=chores_awaiting,
                           redemptions_awaiting=redemptions_awaiting,
                           recent_achievements=recent_achievements,
                           available_rewards=available_rewards,
                           leaderboard=leaderboard,
                           my_points=my_points,
                           is_parent=is_parent,
                           child_summaries=child_summaries)


# ========== CHORES ==========

@bp.route('/rewards/chores', methods=['GET', 'POST'])
@login_required
@active_family_required
def chores():
    family = current_user.get_active_family()
    is_parent = _is_parent()
    form = ChoreForm()
    form.assigned_to.choices = [(0, 'Open (anyone can claim)')] + _family_members()

    if form.validate_on_submit():
        if not is_parent:
            flash('Only parents can add chores.', 'warning')
            return redirect(url_for('rewards.chores'))
        chore = Chore(
            family_id=family.id,
            created_by=current_user.id,
            assigned_to=form.assigned_to.data if form.assigned_to.data != 0 else None,
            title=form.title.data,
            description=form.description.data,
            points=form.points.data,
            due_date=form.due_date.data,
            recurring=form.recurring.data
        )
        db.session.add(chore)
        db.session.commit()
        flash('Chore added!', 'success')
        return redirect(url_for('rewards.chores'))

    tab = request.args.get('tab', 'mine')
    if tab == 'completed':
        chore_list = Chore.query.filter_by(family_id=family.id, status='completed').order_by(
            Chore.completed_at.desc()
        ).limit(50).all()
    elif tab == 'approval':
        chore_list = Chore.query.filter_by(family_id=family.id, status='awaiting_approval').order_by(
            Chore.completed_at.desc()
        ).all()
    elif tab == 'open':
        chore_list = Chore.query.filter_by(
            family_id=family.id, status='pending', assigned_to=None
        ).order_by(
            Chore.due_date.asc().nullslast(), Chore.created_at.desc()
        ).all()
    else:
        # 'mine' — assigned to current user
        chore_list = Chore.query.filter(
            Chore.family_id == family.id,
            Chore.status == 'pending',
            Chore.assigned_to == current_user.id
        ).order_by(
            Chore.due_date.asc().nullslast(), Chore.created_at.desc()
        ).all()

    approval_count = Chore.query.filter_by(family_id=family.id, status='awaiting_approval').count()
    open_count = Chore.query.filter_by(family_id=family.id, status='pending', assigned_to=None).count()

    return render_template('rewards/chores.html', title='Chores',
                           chores=chore_list, form=form, tab=tab,
                           is_parent=is_parent, approval_count=approval_count,
                           open_count=open_count)


@bp.route('/rewards/chores/<int:id>/complete', methods=['POST'])
@login_required
@active_family_required
def complete_chore(id):
    chore = Chore.query.get_or_404(id)
    family = current_user.get_active_family()
    if chore.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.chores'))

    is_parent = _is_parent()
    now = datetime.utcnow()
    is_claim = chore.assigned_to is None

    # Claiming assigns the chore to this user
    if is_claim:
        chore.assigned_to = current_user.id

    if is_parent:
        # Parents complete immediately
        chore.status = 'completed'
        chore.completed_at = now
        chore.completed_by = current_user.id
        if chore.points and chore.points > 0:
            _add_points(current_user.id, family.id, chore.points,
                        'chore', chore.id, f'Completed chore: {chore.title}')
        _spawn_next_chore(chore)
        db.session.commit()
        msg = f'Claimed & completed!' if is_claim else f'Chore completed!'
        flash(f'{msg} +{chore.points} points', 'success')
    else:
        # Children submit for approval
        chore.status = 'awaiting_approval'
        chore.completed_at = now
        chore.completed_by = current_user.id
        db.session.commit()
        msg = 'Chore claimed! Waiting for parent approval.' if is_claim else 'Chore submitted for approval!'
        flash(msg, 'info')

    return redirect(url_for('rewards.chores'))


@bp.route('/rewards/chores/<int:id>/approve', methods=['POST'])
@login_required
@active_family_required
def approve_chore(id):
    if not _is_parent():
        flash('Only parents can approve chores.', 'warning')
        return redirect(url_for('rewards.chores'))

    chore = Chore.query.get_or_404(id)
    family = current_user.get_active_family()
    if chore.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.chores'))

    chore.status = 'completed'
    if chore.points > 0:
        target = chore.completed_by or chore.assigned_to or current_user.id
        _add_points(target, family.id, chore.points,
                    'chore', chore.id, f'Completed chore: {chore.title}')
    _spawn_next_chore(chore)
    db.session.commit()
    completer = User.query.get(chore.completed_by) if chore.completed_by else None
    name = completer.username if completer else 'Unknown'
    flash(f'Approved! {name} earned {chore.points} points.', 'success')
    return redirect(url_for('rewards.chores', tab='approval'))


@bp.route('/rewards/chores/<int:id>/reject', methods=['POST'])
@login_required
@active_family_required
def reject_chore(id):
    if not _is_parent():
        flash('Only parents can reject chores.', 'warning')
        return redirect(url_for('rewards.chores'))

    chore = Chore.query.get_or_404(id)
    family = current_user.get_active_family()
    if chore.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.chores'))

    chore.status = 'pending'
    chore.completed_at = None
    chore.completed_by = None
    db.session.commit()
    flash('Chore sent back to pending.', 'warning')
    return redirect(url_for('rewards.chores', tab='approval'))


@bp.route('/rewards/chores/<int:id>/delete', methods=['POST'])
@login_required
@active_family_required
def delete_chore(id):
    if not _is_parent():
        flash('Only parents can delete chores.', 'warning')
        return redirect(url_for('rewards.chores'))
    chore = Chore.query.get_or_404(id)
    family = current_user.get_active_family()
    if chore.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.chores'))
    db.session.delete(chore)
    db.session.commit()
    flash('Chore deleted.', 'danger')
    return redirect(url_for('rewards.chores'))


@bp.route('/rewards/chores/history')
@login_required
@active_family_required
def chore_history():
    family = current_user.get_active_family()
    member_filter = request.args.get('member', 0, type=int)

    query = Chore.query.filter_by(family_id=family.id, status='completed')
    if member_filter:
        query = query.filter(
            (Chore.assigned_to == member_filter) | (Chore.completed_by == member_filter)
        )
    history = query.order_by(Chore.completed_at.desc()).limit(100).all()
    members = _family_members()

    return render_template('rewards/chore_history.html', title='Chore History',
                           history=history, members=members,
                           member_filter=member_filter)


# ========== ACHIEVEMENTS ==========

@bp.route('/rewards/achievements', methods=['GET', 'POST'])
@login_required
@active_family_required
def achievements():
    family = current_user.get_active_family()
    is_parent = _is_parent()
    form = AchievementForm()
    form.user_id.choices = _family_members()

    if form.validate_on_submit():
        if not is_parent:
            flash('Only parents can award achievements.', 'warning')
            return redirect(url_for('rewards.achievements'))
        achievement = Achievement(
            family_id=family.id,
            user_id=form.user_id.data,
            awarded_by=current_user.id,
            title=form.title.data,
            description=form.description.data,
            icon=form.icon.data,
            points=form.points.data
        )
        db.session.add(achievement)
        if achievement.points > 0:
            _add_points(form.user_id.data, family.id, achievement.points,
                        'achievement', None, f'Achievement: {form.title.data}')
        db.session.commit()
        flash('Achievement awarded!', 'success')
        return redirect(url_for('rewards.achievements'))

    achievement_list = Achievement.query.filter_by(family_id=family.id).order_by(
        Achievement.date_earned.desc()
    ).all()

    return render_template('rewards/achievements.html', title='Achievements',
                           achievements=achievement_list, form=form,
                           is_parent=is_parent)


@bp.route('/rewards/achievements/<int:id>/delete', methods=['POST'])
@login_required
@active_family_required
def delete_achievement(id):
    if not _is_parent():
        flash('Only parents can remove achievements.', 'warning')
        return redirect(url_for('rewards.achievements'))
    achievement = Achievement.query.get_or_404(id)
    family = current_user.get_active_family()
    if achievement.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.achievements'))
    db.session.delete(achievement)
    db.session.commit()
    flash('Achievement removed.', 'danger')
    return redirect(url_for('rewards.achievements'))


# ========== REWARDS SHOP ==========

@bp.route('/rewards/shop', methods=['GET', 'POST'])
@login_required
@active_family_required
def rewards_shop():
    family = current_user.get_active_family()
    is_parent = _is_parent()
    form = RewardForm()

    if form.validate_on_submit():
        if not is_parent:
            flash('Only parents can create rewards.', 'warning')
            return redirect(url_for('rewards.rewards_shop'))
        reward = Reward(
            family_id=family.id,
            created_by=current_user.id,
            title=form.title.data,
            description=form.description.data,
            points_cost=form.points_cost.data,
            icon=form.icon.data,
            available=form.available.data
        )
        db.session.add(reward)
        db.session.commit()
        flash('Reward created!', 'success')
        return redirect(url_for('rewards.rewards_shop'))

    rewards = Reward.query.filter_by(family_id=family.id).order_by(Reward.points_cost.asc()).all()
    my_points = _user_points(current_user.id, family.id)

    pending_redemptions = db.session.query(RewardRedemption).join(Reward).filter(
        Reward.family_id == family.id, RewardRedemption.status == 'pending'
    ).count()

    return render_template('rewards/shop.html', title='Rewards Shop',
                           rewards=rewards, form=form, my_points=my_points,
                           is_parent=is_parent, pending_redemptions=pending_redemptions)


@bp.route('/rewards/shop/<int:id>/redeem', methods=['POST'])
@login_required
@active_family_required
def redeem_reward(id):
    reward = Reward.query.get_or_404(id)
    family = current_user.get_active_family()
    if reward.family_id != family.id or not reward.available:
        flash('This reward is not available.', 'danger')
        return redirect(url_for('rewards.rewards_shop'))

    my_points = _user_points(current_user.id, family.id)
    if my_points < reward.points_cost:
        flash('Not enough points!', 'warning')
        return redirect(url_for('rewards.rewards_shop'))

    is_parent = _is_parent()
    redemption = RewardRedemption(
        reward_id=reward.id, user_id=current_user.id, points_spent=reward.points_cost,
        status='approved' if is_parent else 'pending'
    )
    db.session.add(redemption)
    _add_points(current_user.id, family.id, -reward.points_cost,
                'redemption', reward.id, f'Redeemed: {reward.title}')
    db.session.commit()
    if is_parent:
        flash(f'Redeemed "{reward.title}"! -{reward.points_cost} points', 'success')
    else:
        flash(f'Requested "{reward.title}"! Waiting for parent approval.', 'info')
    return redirect(url_for('rewards.rewards_shop'))


@bp.route('/rewards/shop/<int:id>/delete', methods=['POST'])
@login_required
@active_family_required
def delete_reward(id):
    if not _is_parent():
        flash('Only parents can delete rewards.', 'warning')
        return redirect(url_for('rewards.rewards_shop'))
    reward = Reward.query.get_or_404(id)
    family = current_user.get_active_family()
    if reward.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.rewards_shop'))
    db.session.delete(reward)
    db.session.commit()
    flash('Reward deleted.', 'danger')
    return redirect(url_for('rewards.rewards_shop'))


@bp.route('/rewards/redemptions')
@login_required
@active_family_required
def redemption_history():
    family = current_user.get_active_family()
    is_parent = _is_parent()
    member_filter = request.args.get('member', 0, type=int)
    tab = request.args.get('tab', 'all')

    query = db.session.query(RewardRedemption).join(Reward).filter(
        Reward.family_id == family.id
    )
    if tab == 'pending':
        query = query.filter(RewardRedemption.status == 'pending')
    elif tab == 'approved':
        query = query.filter(RewardRedemption.status == 'approved')
    elif tab == 'rejected':
        query = query.filter(RewardRedemption.status == 'rejected')
    if member_filter:
        query = query.filter(RewardRedemption.user_id == member_filter)
    redemptions = query.order_by(RewardRedemption.redeemed_at.desc()).limit(100).all()
    members = _family_members()
    my_points = _user_points(current_user.id, family.id)

    pending_count = db.session.query(RewardRedemption).join(Reward).filter(
        Reward.family_id == family.id, RewardRedemption.status == 'pending'
    ).count()

    return render_template('rewards/redemption_history.html', title='Redemption History',
                           redemptions=redemptions, members=members,
                           member_filter=member_filter, my_points=my_points,
                           is_parent=is_parent, tab=tab,
                           pending_count=pending_count)


@bp.route('/rewards/redemptions/<int:id>/approve', methods=['POST'])
@login_required
@active_family_required
def approve_redemption(id):
    if not _is_parent():
        flash('Only parents can approve redemptions.', 'warning')
        return redirect(url_for('rewards.redemption_history'))

    redemption = RewardRedemption.query.get_or_404(id)
    family = current_user.get_active_family()
    if redemption.reward.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.redemption_history'))

    redemption.status = 'approved'
    db.session.commit()
    flash(f'Approved "{redemption.reward.title}" for {redemption.user.username}!', 'success')
    return redirect(url_for('rewards.redemption_history', tab='pending'))


@bp.route('/rewards/redemptions/<int:id>/reject', methods=['POST'])
@login_required
@active_family_required
def reject_redemption(id):
    if not _is_parent():
        flash('Only parents can reject redemptions.', 'warning')
        return redirect(url_for('rewards.redemption_history'))

    redemption = RewardRedemption.query.get_or_404(id)
    family = current_user.get_active_family()
    if redemption.reward.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.redemption_history'))

    redemption.status = 'rejected'
    # Refund the points
    _add_points(redemption.user_id, family.id, redemption.points_spent,
                'refund', redemption.reward_id,
                f'Refund: {redemption.reward.title} rejected')
    db.session.commit()
    flash(f'Rejected and refunded {redemption.points_spent} points to {redemption.user.username}.', 'warning')
    return redirect(url_for('rewards.redemption_history', tab='pending'))


# ========== BEHAVIOUR CHART ==========

@bp.route('/rewards/behaviour', methods=['GET', 'POST'])
@login_required
@active_family_required
def behaviour():
    family = current_user.get_active_family()
    is_parent = _is_parent()
    form = BehaviourForm()
    members = _family_members()
    form.user_id.choices = members

    if form.validate_on_submit():
        if not is_parent:
            flash('Only parents can record behaviour.', 'warning')
            return redirect(url_for('rewards.behaviour'))
        points_map = {1: 0, 2: 1, 3: 3, 4: 5, 5: 10}
        pts = points_map.get(form.rating.data, 0)

        # Upsert: replace existing entry for same user+date
        existing = BehaviourEntry.query.filter_by(
            family_id=family.id, user_id=form.user_id.data, date=form.date.data
        ).first()
        if existing:
            # Reverse old points
            if existing.points and existing.points > 0:
                _add_points(existing.user_id, family.id, -existing.points,
                            'behaviour', None, f'Behaviour rating updated')
            existing.rating = form.rating.data
            existing.notes = form.notes.data
            existing.points = pts
            existing.recorded_by = current_user.id
        else:
            entry = BehaviourEntry(
                family_id=family.id,
                user_id=form.user_id.data,
                recorded_by=current_user.id,
                date=form.date.data,
                rating=form.rating.data,
                notes=form.notes.data,
                points=pts
            )
            db.session.add(entry)
        if pts > 0:
            _add_points(form.user_id.data, family.id, pts,
                        'behaviour', None, f'Behaviour rating: {form.rating.data}/5')
        db.session.commit()
        flash('Behaviour entry saved!', 'success')
        return redirect(url_for('rewards.behaviour'))

    # Weekly view
    week_offset = request.args.get('week', 0, type=int)
    today = date.today()
    # Monday of the current week
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # Get child members (role == 'member')
    child_members = []
    for uid, uname in members:
        fm = FamilyMembers.query.filter_by(user_id=uid, family_id=family.id).first()
        if fm and fm.role_in_family == 'member':
            child_members.append((uid, uname))
    # If no members with 'member' role, show all members (fallback)
    if not child_members:
        child_members = members

    # Fetch all entries for this week
    entries = BehaviourEntry.query.filter(
        BehaviourEntry.family_id == family.id,
        BehaviourEntry.date >= start_of_week,
        BehaviourEntry.date <= end_of_week
    ).all()

    # Build lookup: (user_id, date) -> entry
    entry_map = {}
    for e in entries:
        entry_map[(e.user_id, e.date)] = e

    # Build grid: list of {user_id, username, days: [{date, entry_or_none}], week_avg}
    grid = []
    for uid, uname in child_members:
        days = []
        total = 0
        count = 0
        for d in week_dates:
            entry = entry_map.get((uid, d))
            days.append({'date': d, 'entry': entry})
            if entry:
                total += entry.rating
                count += 1
        avg = round(total / count, 1) if count else None
        grid.append({'user_id': uid, 'username': uname, 'days': days, 'avg': avg, 'count': count})

    return render_template('rewards/behaviour.html', title='Behaviour Chart',
                           grid=grid, form=form, members=members,
                           week_dates=week_dates, start_of_week=start_of_week,
                           end_of_week=end_of_week, week_offset=week_offset,
                           is_parent=is_parent, today=today)


@bp.route('/rewards/behaviour/rate', methods=['POST'])
@login_required
@active_family_required
def rate_behaviour():
    """Quick-rate: parent taps a star on the weekly grid."""
    if not _is_parent():
        flash('Only parents can rate behaviour.', 'warning')
        return redirect(url_for('rewards.behaviour'))

    family = current_user.get_active_family()
    user_id = request.form.get('user_id', type=int)
    rate_date = request.form.get('date')
    rating = request.form.get('rating', type=int)
    week_offset = request.form.get('week', 0, type=int)

    if not all([user_id, rate_date, rating]) or rating < 1 or rating > 5:
        flash('Invalid rating.', 'danger')
        return redirect(url_for('rewards.behaviour', week=week_offset))

    rate_date = date.fromisoformat(rate_date)
    points_map = {1: 0, 2: 1, 3: 3, 4: 5, 5: 10}
    pts = points_map.get(rating, 0)

    existing = BehaviourEntry.query.filter_by(
        family_id=family.id, user_id=user_id, date=rate_date
    ).first()

    if existing:
        if existing.points and existing.points > 0:
            _add_points(existing.user_id, family.id, -existing.points,
                        'behaviour', None, 'Behaviour rating updated')
        existing.rating = rating
        existing.points = pts
        existing.recorded_by = current_user.id
    else:
        entry = BehaviourEntry(
            family_id=family.id, user_id=user_id,
            recorded_by=current_user.id, date=rate_date,
            rating=rating, points=pts
        )
        db.session.add(entry)

    if pts > 0:
        _add_points(user_id, family.id, pts,
                    'behaviour', None, f'Behaviour rating: {rating}/5')
    db.session.commit()
    return redirect(url_for('rewards.behaviour', week=week_offset))


@bp.route('/rewards/behaviour/<int:id>/delete', methods=['POST'])
@login_required
@active_family_required
def delete_behaviour(id):
    if not _is_parent():
        flash('Only parents can delete behaviour entries.', 'warning')
        return redirect(url_for('rewards.behaviour'))
    entry = BehaviourEntry.query.get_or_404(id)
    family = current_user.get_active_family()
    if entry.family_id != family.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('rewards.behaviour'))
    db.session.delete(entry)
    db.session.commit()
    flash('Behaviour entry deleted.', 'danger')
    return redirect(url_for('rewards.behaviour'))


# ========== CHILD DASHBOARD (Parent View) ==========

def _child_members(family_id):
    """Return child members (role == 'member') in the family."""
    fms = FamilyMembers.query.filter_by(family_id=family_id, role_in_family='member').all()
    child_ids = [fm.user_id for fm in fms]
    if not child_ids:
        # Fallback: all members
        fms = FamilyMembers.query.filter_by(family_id=family_id).all()
        child_ids = [fm.user_id for fm in fms]
    return User.query.filter(User.id.in_(child_ids)).order_by(User.username).all()


def _calculate_streak(user_id, family_id):
    """Calculate the current chore completion streak (consecutive days)."""
    completed = db.session.query(
        func.date(Chore.completed_at)
    ).filter(
        Chore.family_id == family_id,
        Chore.status == 'completed',
        and_(
            Chore.completed_by == user_id,
            Chore.completed_at.isnot(None)
        )
    ).distinct().order_by(func.date(Chore.completed_at).desc()).all()

    if not completed:
        return 0

    dates = sorted(set(row[0] for row in completed if row[0]), reverse=True)
    if not dates:
        return 0

    streak = 1
    for i in range(1, len(dates)):
        prev = dates[i - 1]
        curr = dates[i]
        if isinstance(prev, str):
            prev = date.fromisoformat(prev)
        if isinstance(curr, str):
            curr = date.fromisoformat(curr)
        if (prev - curr).days == 1:
            streak += 1
        else:
            break
    return streak


@bp.route('/rewards/child/<int:user_id>')
@login_required
@active_family_required
def child_dashboard(user_id):
    """Comprehensive parent view of a child's rewards activity."""
    if not _is_parent():
        flash('Only parents can view child dashboards.', 'warning')
        return redirect(url_for('rewards.rewards_hub'))

    family = current_user.get_active_family()
    child = User.query.get_or_404(user_id)

    # Verify child is in this family
    fm = FamilyMembers.query.filter_by(user_id=user_id, family_id=family.id).first()
    if not fm:
        flash('This user is not in your family.', 'danger')
        return redirect(url_for('rewards.rewards_hub'))

    # Points
    total_points = _user_points(user_id, family.id)

    # Points breakdown by source
    points_by_source = db.session.query(
        PointsLedger.source_type,
        func.coalesce(func.sum(PointsLedger.points), 0)
    ).filter_by(
        user_id=user_id, family_id=family.id
    ).group_by(PointsLedger.source_type).all()
    points_breakdown = dict(points_by_source)

    # Recent points activity (last 20)
    recent_points = PointsLedger.query.filter_by(
        user_id=user_id, family_id=family.id
    ).order_by(PointsLedger.created_at.desc()).limit(20).all()

    # Points earned per week (last 8 weeks)
    eight_weeks_ago = date.today() - timedelta(weeks=8)
    weekly_points = db.session.query(
        func.strftime('%Y-%W', PointsLedger.created_at).label('week'),
        func.sum(PointsLedger.points).label('total')
    ).filter(
        PointsLedger.user_id == user_id,
        PointsLedger.family_id == family.id,
        PointsLedger.created_at >= eight_weeks_ago.isoformat()
    ).group_by('week').order_by('week').all()

    # Chore stats
    chores_completed = Chore.query.filter_by(
        family_id=family.id, status='completed', completed_by=user_id
    ).count()
    chores_pending = Chore.query.filter(
        Chore.family_id == family.id,
        Chore.status == 'pending',
        Chore.assigned_to == user_id
    ).count()
    chores_awaiting = Chore.query.filter_by(
        family_id=family.id, status='awaiting_approval', completed_by=user_id
    ).count()

    # Recent completed chores
    recent_chores = Chore.query.filter_by(
        family_id=family.id, status='completed', completed_by=user_id
    ).order_by(Chore.completed_at.desc()).limit(10).all()

    # Streak
    streak = _calculate_streak(user_id, family.id)

    # Behaviour stats (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    behaviour_entries = BehaviourEntry.query.filter(
        BehaviourEntry.family_id == family.id,
        BehaviourEntry.user_id == user_id,
        BehaviourEntry.date >= thirty_days_ago
    ).order_by(BehaviourEntry.date.desc()).all()

    behaviour_avg = None
    if behaviour_entries:
        behaviour_avg = round(sum(e.rating for e in behaviour_entries) / len(behaviour_entries), 1)

    # Achievements
    achievements = Achievement.query.filter_by(
        family_id=family.id, user_id=user_id
    ).order_by(Achievement.date_earned.desc()).all()

    # Redemptions
    redemptions = db.session.query(RewardRedemption).join(Reward).filter(
        Reward.family_id == family.id,
        RewardRedemption.user_id == user_id
    ).order_by(RewardRedemption.redeemed_at.desc()).limit(10).all()

    # All children for nav tabs
    children = _child_members(family.id)

    return render_template('rewards/child_dashboard.html',
                           title=f"{child.username}'s Dashboard",
                           child=child,
                           children=children,
                           total_points=total_points,
                           points_breakdown=points_breakdown,
                           recent_points=recent_points,
                           weekly_points=weekly_points,
                           chores_completed=chores_completed,
                           chores_pending=chores_pending,
                           chores_awaiting=chores_awaiting,
                           recent_chores=recent_chores,
                           streak=streak,
                           behaviour_entries=behaviour_entries,
                           behaviour_avg=behaviour_avg,
                           achievements=achievements,
                           redemptions=redemptions,
                           is_parent=True)


# ========== POINTS HISTORY ==========

@bp.route('/rewards/points-history')
@login_required
@active_family_required
def points_history():
    """Full audit trail of point transactions with filters."""
    family = current_user.get_active_family()
    is_parent = _is_parent()
    members = _family_members()

    member_filter = request.args.get('member', 0, type=int)
    source_filter = request.args.get('source', '')
    days_filter = request.args.get('days', 30, type=int)

    query = PointsLedger.query.filter_by(family_id=family.id)

    if not is_parent:
        # Non-parents only see their own history
        query = query.filter_by(user_id=current_user.id)
    elif member_filter:
        query = query.filter_by(user_id=member_filter)

    if source_filter:
        query = query.filter_by(source_type=source_filter)

    if days_filter > 0:
        cutoff = datetime.utcnow() - timedelta(days=days_filter)
        query = query.filter(PointsLedger.created_at >= cutoff)

    entries = query.order_by(PointsLedger.created_at.desc()).limit(200).all()

    # Summary stats
    total_earned = sum(e.points for e in entries if e.points > 0)
    total_spent = sum(e.points for e in entries if e.points < 0)

    return render_template('rewards/points_history.html',
                           title='Points History',
                           entries=entries,
                           members=members,
                           member_filter=member_filter,
                           source_filter=source_filter,
                           days_filter=days_filter,
                           total_earned=total_earned,
                           total_spent=total_spent,
                           is_parent=is_parent)


# ========== UPCOMING CHORES ==========

@bp.route('/rewards/upcoming')
@login_required
@active_family_required
def upcoming_chores():
    """Show future scheduled chores from recurring patterns."""
    family = current_user.get_active_family()
    is_parent = _is_parent()
    members = _family_members()
    member_filter = request.args.get('member', 0, type=int)
    weeks_ahead = request.args.get('weeks', 2, type=int)
    weeks_ahead = min(max(weeks_ahead, 1), 8)  # clamp 1-8

    today = date.today()
    end_date = today + timedelta(weeks=weeks_ahead)

    # Get existing pending chores with due dates
    pending_query = Chore.query.filter(
        Chore.family_id == family.id,
        Chore.status == 'pending',
        Chore.due_date.isnot(None),
        Chore.due_date >= today,
        Chore.due_date <= end_date
    )
    if member_filter:
        pending_query = pending_query.filter(
            (Chore.assigned_to == member_filter) | (Chore.assigned_to.is_(None))
        )
    existing_chores = pending_query.order_by(Chore.due_date.asc()).all()

    # Project future occurrences from the latest recurring chore of each "series"
    # Find the latest pending or completed recurring chore per title+assignee
    recurring_bases = db.session.query(
        Chore.title,
        Chore.assigned_to,
        Chore.points,
        Chore.recurring,
        Chore.description,
        func.max(Chore.due_date).label('latest_due')
    ).filter(
        Chore.family_id == family.id,
        Chore.recurring != 'none',
        Chore.due_date.isnot(None)
    ).group_by(Chore.title, Chore.assigned_to, Chore.points, Chore.recurring, Chore.description).all()

    projected = []
    existing_keys = set()
    for c in existing_chores:
        existing_keys.add((c.title, c.assigned_to, str(c.due_date)))

    for base in recurring_bases:
        if member_filter and base.assigned_to and base.assigned_to != member_filter:
            continue
        latest = base.latest_due
        if isinstance(latest, str):
            latest = date.fromisoformat(latest)
        # Generate future dates
        current_date = latest
        for _ in range(50):  # safety limit
            if base.recurring == 'daily':
                current_date = current_date + timedelta(days=1)
            elif base.recurring == 'weekly':
                current_date = current_date + timedelta(weeks=1)
            elif base.recurring == 'monthly':
                m = current_date.month + 1
                y = current_date.year
                if m > 12:
                    m = 1
                    y += 1
                day = min(current_date.day, 28)
                current_date = current_date.replace(year=y, month=m, day=day)
            else:
                break

            if current_date > end_date:
                break
            if current_date < today:
                continue
            key = (base.title, base.assigned_to, str(current_date))
            if key not in existing_keys:
                assignee = User.query.get(base.assigned_to) if base.assigned_to else None
                projected.append({
                    'title': base.title,
                    'description': base.description,
                    'assigned_to': base.assigned_to,
                    'assignee_name': assignee.username if assignee else 'Unassigned',
                    'points': base.points,
                    'recurring': base.recurring,
                    'due_date': current_date,
                    'is_projected': True
                })

    # Combine and sort by date
    schedule = []
    for c in existing_chores:
        schedule.append({
            'title': c.title,
            'description': c.description,
            'assigned_to': c.assigned_to,
            'assignee_name': c.assignee.username if c.assignee else 'Unassigned',
            'points': c.points,
            'recurring': c.recurring,
            'due_date': c.due_date,
            'is_projected': False,
            'id': c.id
        })
    schedule.extend(projected)
    schedule.sort(key=lambda x: x['due_date'])

    # Group by date
    grouped = defaultdict(list)
    for item in schedule:
        grouped[item['due_date']].append(item)

    return render_template('rewards/upcoming_chores.html',
                           title='Upcoming Chores',
                           grouped=grouped,
                           schedule=schedule,
                           members=members,
                           member_filter=member_filter,
                           weeks_ahead=weeks_ahead,
                           today=today,
                           end_date=end_date,
                           is_parent=is_parent)


# ========== WEEKLY SUMMARY ==========

@bp.route('/rewards/summary')
@login_required
@active_family_required
def weekly_summary():
    """Weekly summary report for parents showing each child's activity."""
    if not _is_parent():
        flash('Only parents can view the weekly summary.', 'warning')
        return redirect(url_for('rewards.rewards_hub'))

    family = current_user.get_active_family()
    week_offset = request.args.get('week', 0, type=int)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)

    children = _child_members(family.id)
    summaries = []

    for child in children:
        # Points earned this week
        week_points = db.session.query(
            func.coalesce(func.sum(PointsLedger.points), 0)
        ).filter(
            PointsLedger.user_id == child.id,
            PointsLedger.family_id == family.id,
            PointsLedger.created_at >= start_of_week.isoformat(),
            PointsLedger.created_at <= (end_of_week + timedelta(days=1)).isoformat()
        ).scalar()

        # Chores completed this week
        chores_done = Chore.query.filter(
            Chore.family_id == family.id,
            Chore.status == 'completed',
            Chore.completed_by == child.id,
            Chore.completed_at >= start_of_week.isoformat(),
            Chore.completed_at <= (end_of_week + timedelta(days=1)).isoformat()
        ).count()

        # Behaviour average this week
        week_behaviour = BehaviourEntry.query.filter(
            BehaviourEntry.family_id == family.id,
            BehaviourEntry.user_id == child.id,
            BehaviourEntry.date >= start_of_week,
            BehaviourEntry.date <= end_of_week
        ).all()
        beh_avg = None
        if week_behaviour:
            beh_avg = round(sum(e.rating for e in week_behaviour) / len(week_behaviour), 1)

        # Achievements this week
        week_achievements = Achievement.query.filter(
            Achievement.family_id == family.id,
            Achievement.user_id == child.id,
            Achievement.date_earned >= start_of_week.isoformat(),
            Achievement.date_earned <= (end_of_week + timedelta(days=1)).isoformat()
        ).count()

        # Rewards redeemed this week
        week_redemptions = db.session.query(RewardRedemption).join(Reward).filter(
            Reward.family_id == family.id,
            RewardRedemption.user_id == child.id,
            RewardRedemption.redeemed_at >= start_of_week.isoformat(),
            RewardRedemption.redeemed_at <= (end_of_week + timedelta(days=1)).isoformat()
        ).count()

        # Streak
        streak = _calculate_streak(child.id, family.id)

        # Total points
        total_points = _user_points(child.id, family.id)

        summaries.append({
            'child': child,
            'week_points': week_points,
            'total_points': total_points,
            'chores_done': chores_done,
            'behaviour_avg': beh_avg,
            'behaviour_entries': len(week_behaviour),
            'achievements': week_achievements,
            'redemptions': week_redemptions,
            'streak': streak
        })

    return render_template('rewards/weekly_summary.html',
                           title='Weekly Summary',
                           summaries=summaries,
                           start_of_week=start_of_week,
                           end_of_week=end_of_week,
                           week_offset=week_offset,
                           is_parent=True)
