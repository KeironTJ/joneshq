from app.family_manager import bp
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from datetime import datetime, timedelta
from app.models import User, Family, FamilyMembers
from app.family_manager.forms import FamilySelectForm, FamilyCreateorJoinForm
from sqlalchemy.orm import joinedload
from app.decorators import active_family_required
from app.family_manager.helper import create_or_join_family

@bp.route('/family_home/<family_name>', methods=['GET', 'POST'])
@login_required
@active_family_required
def family_home(family_name):
    family = Family.query.filter_by(name=family_name).options(joinedload(Family.members)).first_or_404()
    if not family:
        flash('Family not found.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('family_manager/family_home.html',
                           family=family,
                           family_name=family_name,
                           title='Family Home')

@bp.route('/family_choose', methods=['GET', 'POST'])
@login_required
def family_choose():
    form = FamilySelectForm()
    form.family.choices = [(family.id, family.name) for family in current_user.families]

    if form.validate_on_submit():
        # Set the selected family as the active family
        family_id = form.family.data

        if current_user.set_active_family(family_id):
            db.session.commit()
            flash("Active family updated successfully.", "success")

        else:
            flash("Failed to update active family.", "danger")
        return redirect(url_for('main.dashboard'))


    return render_template('family_manager/family_choose.html',
                           title='Choose Family',
                           form=form)   

@bp.route('/create_or_join_family_view', methods=['GET', 'POST'])
@login_required
def create_or_join_family_view():
    form = FamilyCreateorJoinForm()  # You can reuse or create a new form for this purpose

    if form.validate_on_submit():

        # Handle family creation or joining
        create_or_join = form.create_or_join.data
        family_name = form.family_name.data if create_or_join == 'create' else None
        invitation_code = form.invitation_code.data if create_or_join == 'join' else None

        if create_or_join_family(current_user, create_or_join, family_name, invitation_code):
            return redirect(url_for('main.dashboard'))

    return render_template('family_manager/create_or_join_family_view.html', 
                           title='Create or Join Family', 
                           form=form)


@bp.route('/family_home/<family_name>/change_role/<int:member_id>', methods=['POST'])
@login_required
@active_family_required
def change_role(family_name, member_id):
    family = Family.query.filter_by(name=family_name).first_or_404()

    # Check caller is owner or co-owner
    caller_fm = FamilyMembers.query.filter_by(
        user_id=current_user.id, family_id=family.id
    ).first()
    if not caller_fm or caller_fm.role_in_family not in ('owner', 'co-owner'):
        flash('Only owners and co-owners can change roles.', 'danger')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    target_fm = FamilyMembers.query.filter_by(
        user_id=member_id, family_id=family.id
    ).first_or_404()

    new_role = request.form.get('role', '').strip().lower()
    allowed_roles = ['member', 'co-owner']

    # Only the owner can promote someone to owner (transfers ownership)
    if new_role == 'owner' and caller_fm.role_in_family == 'owner':
        # Transfer ownership
        caller_fm.role_in_family = 'co-owner'
        target_fm.role_in_family = 'owner'
        family.owner_id = member_id
        db.session.commit()
        flash(f'Ownership transferred to {target_fm.user.username}.', 'success')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    if new_role not in allowed_roles:
        flash('Invalid role.', 'danger')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    # Cannot change the owner's role (must use transfer above)
    if target_fm.role_in_family == 'owner':
        flash('Cannot change the owner\'s role. Transfer ownership instead.', 'warning')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    # Co-owners cannot change other co-owners
    if caller_fm.role_in_family == 'co-owner' and target_fm.role_in_family == 'co-owner':
        flash('Co-owners cannot change other co-owners\' roles.', 'warning')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    target_fm.role_in_family = new_role
    db.session.commit()
    flash(f'{target_fm.user.username}\'s role changed to {new_role}.', 'success')
    return redirect(url_for('family_manager.family_home', family_name=family_name))


@bp.route('/family_home/<family_name>/remove_member/<int:member_id>', methods=['POST'])
@login_required
@active_family_required
def remove_member(family_name, member_id):
    family = Family.query.filter_by(name=family_name).first_or_404()

    caller_fm = FamilyMembers.query.filter_by(
        user_id=current_user.id, family_id=family.id
    ).first()
    if not caller_fm or caller_fm.role_in_family not in ('owner', 'co-owner'):
        flash('Only owners and co-owners can remove members.', 'danger')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    if member_id == current_user.id:
        flash('You cannot remove yourself.', 'warning')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    target_fm = FamilyMembers.query.filter_by(
        user_id=member_id, family_id=family.id
    ).first_or_404()

    # Cannot remove the owner
    if target_fm.role_in_family == 'owner':
        flash('Cannot remove the family owner.', 'danger')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    # Co-owners cannot remove other co-owners
    if caller_fm.role_in_family == 'co-owner' and target_fm.role_in_family == 'co-owner':
        flash('Co-owners cannot remove other co-owners.', 'warning')
        return redirect(url_for('family_manager.family_home', family_name=family_name))

    username = target_fm.user.username
    # Clear active family if it was this one
    target_user = User.query.get(member_id)
    if target_user and target_user.active_family_id == family.id:
        target_user.active_family_id = None

    db.session.delete(target_fm)
    db.session.commit()
    flash(f'{username} has been removed from the family.', 'info')
    return redirect(url_for('family_manager.family_home', family_name=family_name))