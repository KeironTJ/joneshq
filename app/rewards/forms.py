from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, DateField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ChoreForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    assigned_to = SelectField('Assign To', coerce=int, validators=[Optional()])
    points = IntegerField('Points', default=0, validators=[NumberRange(min=0, max=1000)])
    due_date = DateField('Due Date', validators=[Optional()])
    recurring = SelectField('Recurring', choices=[
        ('none', 'One-time'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')
    ], default='none')
    submit = SubmitField('Save Chore')


class AchievementForm(FlaskForm):
    user_id = SelectField('Award To', coerce=int, validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    icon = SelectField('Icon', choices=[
        ('fa-trophy', 'Trophy'), ('fa-star', 'Star'), ('fa-medal', 'Medal'),
        ('fa-award', 'Award'), ('fa-crown', 'Crown'), ('fa-thumbs-up', 'Thumbs Up'),
        ('fa-fire', 'Fire'), ('fa-bolt', 'Lightning'), ('fa-heart', 'Heart'),
        ('fa-graduation-cap', 'Graduation')
    ], default='fa-trophy')
    points = IntegerField('Points', default=0, validators=[NumberRange(min=0, max=1000)])
    submit = SubmitField('Award Achievement')


class RewardForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    points_cost = IntegerField('Points Cost', validators=[DataRequired(), NumberRange(min=1, max=10000)])
    icon = SelectField('Icon', choices=[
        ('fa-gift', 'Gift'), ('fa-gamepad', 'Gamepad'), ('fa-ice-cream', 'Ice Cream'),
        ('fa-film', 'Movie'), ('fa-money-bill', 'Money'), ('fa-pizza-slice', 'Pizza'),
        ('fa-couch', 'Day Off'), ('fa-music', 'Music'), ('fa-shopping-bag', 'Shopping'),
        ('fa-plane', 'Trip')
    ], default='fa-gift')
    available = BooleanField('Available', default=True)
    submit = SubmitField('Save Reward')


class BehaviourForm(FlaskForm):
    user_id = SelectField('Family Member', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    rating = SelectField('Rating', coerce=int, choices=[
        (5, 'Excellent'), (4, 'Great'), (3, 'Good'), (2, 'Needs Work'), (1, 'Poor')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Length(max=500)])
    submit = SubmitField('Save Entry')
