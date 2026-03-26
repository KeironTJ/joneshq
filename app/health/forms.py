from flask_wtf import FlaskForm
from wtforms import SelectField, FloatField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional


class HealthLogForm(FlaskForm):
    category = SelectField('Category', choices=[
        ('weight', 'Weight (lbs)'),
        ('exercise', 'Exercise (minutes)'),
        ('water', 'Water Intake (litres)'),
        ('sleep', 'Sleep (hours)'),
        ('mood', 'Mood (1-5)')
    ], validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    value = FloatField('Value', validators=[DataRequired(), NumberRange(min=0)])
    notes = TextAreaField('Notes', validators=[Length(max=500)])
    submit = SubmitField('Log Entry')
