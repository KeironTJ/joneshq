from flask_wtf import FlaskForm 
from wtforms import (
    TextAreaField,
    DateField,
    SubmitField,
    SelectField,
    StringField,
    BooleanField,
    PasswordField,
    ValidationError,
)
from wtforms.validators import DataRequired, Length
from app.models import User, Role
from app import db
import sqlalchemy as sa


## Site Banner
class SiteBannerForm(FlaskForm):
    title = StringField('Banner Title', validators=[DataRequired(), Length(max=100)])
    message = TextAreaField('Banner Message', validators=[DataRequired(), Length(max=500)])
    banner_type = SelectField(
        'Banner Style',
        choices=[
            ('info', 'Info (Blue)'),
            ('warning', 'Warning (Yellow)'),
            ('success', 'Success (Green)'),
            ('danger', 'Danger (Red)'),
            ('development', 'Development (Teal)'),
        ],
        validators=[DataRequired()],
    )
    show_on_index = BooleanField('Show on Index Page')
    show_on_all_pages = BooleanField('Show on All Pages')
    is_active = BooleanField('Banner Active')
    submit = SubmitField('Save Banner')


## MealPlanner
class AddMealForm(FlaskForm):
    meal_date = DateField(
        'Meal Date',
        validators=[DataRequired(message="Please enter a valid date")]
    )
    meal_description = TextAreaField(
        'Meal Description',
        validators=[
            DataRequired(message="Meal description cannot be empty"),
            Length(max=500, message="Meal description cannot exceed 500 characters")
        ]
    )
    meal_source = TextAreaField(
        'Meal Source',
        validators=[
            Length(max=500, message="Meal source cannot exceed 500 characters")
        ]
    )
    add_meal = SubmitField('Add Meal')

# Assign Role Form
class AssignRoleForm(FlaskForm):
    username = SelectField('Username', validators=[DataRequired()], choices=[])
    role = SelectField('Role', validators=[DataRequired()], choices=[])
    assign = SubmitField('Assign Role')
    unassign = SubmitField('Unassign Role')

    def __init__(self, *args, **kwargs):
        super(AssignRoleForm, self).__init__(*args, **kwargs)
        self.username.choices = [
            (user.username, user.username) for user in db.session.scalars(sa.select(User)).all()
        ]
        self.role.choices = [
            (role.name, role.name) for role in db.session.scalars(sa.select(Role)).all()
        ]

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is None:
            raise ValidationError('User does not exist.')

    def validate_role(self, role):
        role_names = [role.name for role in db.session.scalars(sa.select(Role)).all()]
        if role.data not in role_names:
            raise ValidationError('Invalid role.')


class DeleteUserForm(FlaskForm):
    submit = SubmitField('Delete')


class DeleteFamilyForm(FlaskForm):
    family_id = SelectField('Family', validators=[DataRequired()], choices=[], coerce=int)
    submit = SubmitField('Delete Family')


class TransferFamilyOwnershipForm(FlaskForm):
    family_id = SelectField('Family', validators=[DataRequired()], choices=[], coerce=int)
    new_owner_id = SelectField('New Owner', validators=[DataRequired()], choices=[], coerce=int)
    submit = SubmitField('Reassign Owner')


class CreateFamilyForm(FlaskForm):
    family_name = StringField('Family Name', validators=[DataRequired(), Length(max=128)])
    submit = SubmitField('Add Family')


class AddUserToFamilyForm(FlaskForm):
    family_id = SelectField('Family', validators=[DataRequired()], choices=[], coerce=int)
    user_id = SelectField('User', validators=[DataRequired()], choices=[], coerce=int)
    role_in_family = SelectField(
        'Role',
        validators=[DataRequired()],
        choices=[('owner', 'Owner'), ('co-owner', 'Co-Owner'), ('member', 'Member')],
    )
    submit = SubmitField('Add User to Family')