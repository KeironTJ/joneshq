
from app import db
from app.models import (
    User,
    Role,
    UserRoles,
    MealPlan,
    Message,
    Family,
    FamilyMembers,
    ActivityPlan,
    SiteBanner,
)
from flask import render_template, flash, redirect, url_for, request, session, jsonify
from flask_login import login_required, current_user 
from app.decorators import admin_required
from app.admin import bp
from app.admin.forms import (
    AddMealForm,
    AssignRoleForm,
    DeleteUserForm,
    DeleteFamilyForm,
    TransferFamilyOwnershipForm,
    CreateFamilyForm,
    AddUserToFamilyForm,
    SiteBannerForm,
)


## Admin Routes
# Displays the admin home page
@bp.route('/admin_home', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_home():

    return render_template('admin/admin_home.html',
                           title='Admin Home')

# Displays the error page when a user is not an admin
@bp.route('/not_admin')
def not_admin():
    return render_template('admin/not_admin.html', title='Not Admin')


# Displays all user information
@bp.route('/admin_users', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_users():
    assignuserroleform = AssignRoleForm()
    delete_user_form = DeleteUserForm()

    users = db.session.query(User).all()
    roles = db.session.query(Role).all()
    user_roles = db.session.query(UserRoles).all()

    if assignuserroleform.validate_on_submit():
        user = db.session.query(User).filter_by(username=assignuserroleform.username.data).first()
        
        if "assign" in request.form:  # Check which button was clicked
            if user and user.assign_user_role(assignuserroleform.role.data):
                db.session.commit()
                flash('Role assigned successfully!', 'success')
            else:
                flash('Invalid user or role.', 'danger')

        elif "unassign" in request.form:  # Check if "Unassign" was clicked
            if user and user.unassign_user_role(assignuserroleform.role.data):
                db.session.commit()

                # Refresh the user_roles query after deletion
                user_roles = db.session.query(UserRoles).all()

                flash('Role unassigned successfully!', 'success')
            else:
                flash('Invalid user or role.', 'danger')


    return render_template('admin/admin_users.html',
                           title='Admin Users',
                           users=users,
                           roles=roles,
                           user_roles=user_roles,
                           assignuserroleform=assignuserroleform,
                           delete_user_form=delete_user_form)


@bp.route('/admin_users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.admin_users'))

    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('admin.admin_users'))

    if user.is_admin():
        flash('Remove admin privileges before deleting this account.', 'warning')
        return redirect(url_for('admin.admin_users'))

    if user.owned_families:
        flash('Reassign or delete families owned by this user before deleting the account.', 'warning')
        return redirect(url_for('admin.admin_users'))

    FamilyMembers.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Message.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    MealPlan.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ActivityPlan.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    user.roles.clear()

    if user.address:
        db.session.delete(user.address)

    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully.', 'success')
    return redirect(url_for('admin.admin_users'))



##Messages
# Displays the admin messages page
@bp.route('/admin_messages', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_messages():

    messages = db.session.query(Message).all()

    return render_template('admin/admin_messages.html', 
                           title='Admin Messages',
                           messages=messages)




## MealPlanner
# Displays the admin mealplanner page
@bp.route('/admin_mealplanner', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_mealplanner():    

    form = AddMealForm()
    mealplan = MealPlan.query.all()

    return render_template('admin/admin_mealplanner.html',
                           title='Admin Meal Planner',
                           mealplan=mealplan, 
                           form=form)

@bp.route('/admin_add_meal', methods=['GET', 'POST'])
@login_required
@admin_required
def add_meal():
    form = AddMealForm()
    if form.validate_on_submit():
        meal = MealPlan(
            user_id=current_user.id,
            meal_date=form.meal_date.data,
            meal_description=form.meal_description.data,
            meal_source=form.meal_source.data
        )
        db.session.add(meal)
        db.session.commit()
        flash('Meal added successfully!', 'success')
        return redirect(url_for('admin.admin_mealplanner'))
    elif request.method == 'POST':
        flash('Please fill in all fields.', 'danger')

    return redirect(url_for('admin.admin_mealplanner'))

@bp.route('/admin_edit_meal/<int:meal_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_meal(meal_id):
    meal = MealPlan.query.get_or_404(meal_id)
    form = AddMealForm()
    if form.validate_on_submit():
        meal.meal_date = form.meal_date.data
        meal.meal_description = form.meal_description.data
        meal.meal_source = form.meal_source.data
        db.session.commit()
        flash("Meal updated successfully!", "success")
    return redirect(url_for('admin.admin_mealplanner'))

@bp.route('/admin_delete_meal/<int:meal_id>', methods=['POST'])
@login_required
@admin_required
def delete_meal(meal_id):
    meal = MealPlan.query.get_or_404(meal_id)
    db.session.delete(meal)
    db.session.commit()
    flash("Meal deleted successfully!", "success")
    return redirect(url_for('admin.admin_mealplanner'))
    

## FAMILIES
@bp.route('/admin_families', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_families():
    users = db.session.query(User).all()
    families = db.session.query(Family).all()
    family_members = db.session.query(FamilyMembers).all()
    create_family_form = CreateFamilyForm()
    add_user_form = AddUserToFamilyForm()
    delete_family_form = DeleteFamilyForm()
    transfer_family_form = TransferFamilyOwnershipForm()

    family_choices = [(family.id, family.name) for family in families]
    add_user_form.family_id.choices = family_choices
    delete_family_form.family_id.choices = family_choices
    transfer_family_form.family_id.choices = family_choices

    user_choices = [(user.id, user.username) for user in users]
    add_user_form.user_id.choices = user_choices
    transfer_family_form.new_owner_id.choices = user_choices

    return render_template('admin/admin_families.html',
                           title='Admin Families',
                           users=users,
                           families=families,
                           family_members=family_members,
                           create_family_form=create_family_form,
                           add_user_form=add_user_form,
                           delete_family_form=delete_family_form,
                           transfer_family_form=transfer_family_form)

@bp.route('/add_family', methods=['POST'])
@login_required
@admin_required
def add_family():
    form = CreateFamilyForm()
    if form.validate_on_submit():
        family_name = form.family_name.data.strip()
        family = Family(name=family_name, owner_id=current_user.id)
        db.session.add(family)
        db.session.commit()
        flash("Family added successfully!", "success")
    else:
        flash("Invalid family name.", "danger")

    return redirect(url_for('admin.admin_families'))



@bp.route('/add_user_to_family', methods=['POST'])
@login_required
@admin_required
def add_user_to_family():
    form = AddUserToFamilyForm()
    families = db.session.query(Family).all()
    users = db.session.query(User).all()
    form.family_id.choices = [(family.id, family.name) for family in families]
    form.user_id.choices = [(user.id, user.username) for user in users]

    if not form.validate_on_submit():
        flash("Invalid user, family, or role selection.", "danger")
        return redirect(url_for('admin.admin_families'))

    user = db.session.get(User, form.user_id.data)
    family = db.session.get(Family, form.family_id.data)
    role_in_family = form.role_in_family.data

    if user and family:
        existing_entry = FamilyMembers.query.filter_by(user_id=user.id, family_id=family.id).first()
        if existing_entry:
            flash("User is already part of this family.", "warning")
        else:
            new_entry = FamilyMembers(user_id=user.id, family_id=family.id, role_in_family=role_in_family)
            db.session.add(new_entry)
            db.session.commit()
            flash(f"User added as {role_in_family} successfully!", "success")
    else:
        flash("Invalid user or family selection.", "danger")

    return redirect(url_for('admin.admin_families'))


@bp.route('/admin_families/delete', methods=['POST'])
@login_required
@admin_required
def delete_family():
    form = DeleteFamilyForm()
    families = db.session.query(Family).all()
    form.family_id.choices = [(family.id, family.name) for family in families]

    if not form.validate_on_submit():
        flash('Invalid family selection.', 'danger')
        return redirect(url_for('admin.admin_families'))

    family = db.session.get(Family, form.family_id.data)
    if not family:
        flash('Family not found.', 'danger')
        return redirect(url_for('admin.admin_families'))

    FamilyMembers.query.filter_by(family_id=family.id).delete(synchronize_session=False)
    affected_users = db.session.query(User).filter_by(active_family_id=family.id).all()
    for user in affected_users:
        user.active_family_id = None

    db.session.delete(family)
    db.session.commit()
    flash('Family deleted successfully.', 'success')
    return redirect(url_for('admin.admin_families'))


@bp.route('/admin_families/reassign_owner', methods=['POST'])
@login_required
@admin_required
def reassign_family_owner():
    form = TransferFamilyOwnershipForm()
    families = db.session.query(Family).all()
    users = db.session.query(User).all()
    form.family_id.choices = [(family.id, family.name) for family in families]
    form.new_owner_id.choices = [(user.id, user.username) for user in users]

    if not form.validate_on_submit():
        flash('Invalid submission. Please select a family and owner.', 'danger')
        return redirect(url_for('admin.admin_families'))

    family = db.session.get(Family, form.family_id.data)
    new_owner = db.session.get(User, form.new_owner_id.data)

    if not family or not new_owner:
        flash('Invalid family or user selection.', 'danger')
        return redirect(url_for('admin.admin_families'))

    membership = FamilyMembers.query.filter_by(user_id=new_owner.id, family_id=family.id).first()
    if not membership:
        flash('Selected user must be a member of the family before ownership transfer.', 'danger')
        return redirect(url_for('admin.admin_families'))

    previous_owner_id = family.owner_id
    family.owner_id = new_owner.id
    membership.role_in_family = 'owner'

    if previous_owner_id and previous_owner_id != new_owner.id:
        previous_membership = FamilyMembers.query.filter_by(user_id=previous_owner_id, family_id=family.id).first()
        if previous_membership:
            previous_membership.role_in_family = 'member'

    if not new_owner.active_family_id:
        new_owner.active_family_id = family.id

    db.session.commit()
    flash('Family owner reassigned successfully.', 'success')
    return redirect(url_for('admin.admin_families'))


## SITE BANNERS
@bp.route('/admin_banners', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_banners():
    form = SiteBannerForm()
    banners = SiteBanner.query.order_by(SiteBanner.created_at.desc()).all()

    if form.validate_on_submit():
        banner = SiteBanner(
            title=form.title.data.strip(),
            message=form.message.data.strip(),
            banner_type=form.banner_type.data,
            show_on_index=form.show_on_index.data,
            show_on_all_pages=form.show_on_all_pages.data,
            is_active=form.is_active.data,
            updated_by=current_user.id,
        )
        db.session.add(banner)
        db.session.commit()
        flash('Banner created successfully!', 'success')
        return redirect(url_for('admin.admin_banners'))

    return render_template('admin/admin_banners.html',
                           title='Manage Banners',
                           form=form,
                           banners=banners)


@bp.route('/admin_banners/edit/<int:banner_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_banner(banner_id):
    banner = SiteBanner.query.get_or_404(banner_id)
    form = SiteBannerForm(obj=banner)

    if form.validate_on_submit():
        banner.title = form.title.data.strip()
        banner.message = form.message.data.strip()
        banner.banner_type = form.banner_type.data
        banner.show_on_index = form.show_on_index.data
        banner.show_on_all_pages = form.show_on_all_pages.data
        banner.is_active = form.is_active.data
        banner.updated_by = current_user.id
        db.session.commit()
        flash('Banner updated!', 'success')
        return redirect(url_for('admin.admin_banners'))

    return render_template('admin/admin_banners.html',
                           title='Edit Banner',
                           form=form,
                           banners=SiteBanner.query.order_by(SiteBanner.created_at.desc()).all(),
                           editing=banner)


@bp.route('/admin_banners/toggle/<int:banner_id>', methods=['POST'])
@login_required
@admin_required
def toggle_banner(banner_id):
    banner = SiteBanner.query.get_or_404(banner_id)
    banner.is_active = not banner.is_active
    db.session.commit()
    state = 'activated' if banner.is_active else 'deactivated'
    flash(f'Banner {state}.', 'success')
    return redirect(url_for('admin.admin_banners'))


@bp.route('/admin_banners/delete/<int:banner_id>', methods=['POST'])
@login_required
@admin_required
def delete_banner(banner_id):
    banner = SiteBanner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    flash('Banner deleted.', 'success')
    return redirect(url_for('admin.admin_banners'))
