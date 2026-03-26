from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, DateField, TextAreaField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional


class HealthLogForm(FlaskForm):
    category = SelectField('Category', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    value = FloatField('Value', validators=[DataRequired(), NumberRange(min=0)])
    notes = TextAreaField('Notes', validators=[Length(max=500)])
    submit = SubmitField('Log Entry')


class HealthCategoryForm(FlaskForm):
    label = StringField('Display Name', validators=[DataRequired(), Length(max=64)])
    unit = StringField('Unit', validators=[DataRequired(), Length(max=20)])
    icon = SelectField('Icon', choices=[
        ('fa-weight-scale', 'Weight Scale'),
        ('fa-person-running', 'Running'),
        ('fa-droplet', 'Water Drop'),
        ('fa-bed', 'Sleep'),
        ('fa-face-smile', 'Mood'),
        ('fa-shoe-prints', 'Steps'),
        ('fa-tv', 'Screen'),
        ('fa-book', 'Reading'),
        ('fa-car', 'Driving'),
        ('fa-apple-whole', 'Fruit/Veg'),
        ('fa-fire', 'Calories'),
        ('fa-om', 'Meditation'),
        ('fa-utensils', 'Meals'),
        ('fa-dumbbell', 'Weights'),
        ('fa-bicycle', 'Cycling'),
        ('fa-swimming-pool', 'Swimming'),
        ('fa-heartbeat', 'Heart Rate'),
        ('fa-pills', 'Medication'),
        ('fa-glass-water', 'Drinks'),
        ('fa-circle', 'Default'),
    ], default='fa-circle')
    color = SelectField('Color', choices=[
        ('#E07A5F', 'Coral'),
        ('#4CAF82', 'Green'),
        ('#5B8DEF', 'Blue'),
        ('#9B6DD7', 'Purple'),
        ('#E8A44A', 'Amber'),
        ('#E25D8B', 'Pink'),
        ('#00BCD4', 'Teal'),
        ('#FF7043', 'Orange'),
        ('#8D6E63', 'Brown'),
        ('#78909C', 'Grey'),
    ], default='#6C757D')
    aggregation = SelectField('Daily Total Method', choices=[
        ('sum', 'Sum entries (e.g. exercise, water)'),
        ('latest', 'Use latest entry (e.g. weight)'),
    ], default='sum')
    daily_goal = FloatField('Daily Goal', validators=[Optional(), NumberRange(min=0)])
    sort_order = IntegerField('Sort Order', default=0, validators=[Optional()])
    submit = SubmitField('Save Category')
