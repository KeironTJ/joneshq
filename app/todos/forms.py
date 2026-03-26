from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, SelectField, DateField,
                     TimeField, IntegerField, SubmitField)
from wtforms.validators import DataRequired, Length, Optional


class TodoListForm(FlaskForm):
    title = StringField('List Name', validators=[DataRequired(), Length(max=128)])
    color = SelectField('Colour', choices=[
        ('#3A8F85', 'Teal'), ('#5B8DEF', 'Blue'), ('#E25D8B', 'Pink'),
        ('#E8A44A', 'Amber'), ('#4CAF82', 'Green'), ('#9B6DD7', 'Purple'),
        ('#E07A5F', 'Coral'), ('#78909C', 'Grey'),
    ], default='#3A8F85')
    icon = SelectField('Icon', choices=[
        ('fa-list-check', 'Checklist'), ('fa-house', 'Home'),
        ('fa-briefcase', 'Work'), ('fa-cart-shopping', 'Shopping'),
        ('fa-graduation-cap', 'School'), ('fa-heart', 'Personal'),
        ('fa-star', 'Starred'), ('fa-plane', 'Travel'),
        ('fa-utensils', 'Food'), ('fa-dumbbell', 'Fitness'),
    ], default='fa-list-check')
    shared = SelectField('Visibility', choices=[
        ('personal', 'Just me'), ('family', 'Shared with family'),
    ], default='personal')
    submit = SubmitField('Save List')


class TodoItemForm(FlaskForm):
    title = StringField('Task', validators=[DataRequired(), Length(max=256)])
    notes = TextAreaField('Notes', validators=[Length(max=1000)])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent'),
    ], default='medium')
    due_date = DateField('Due Date', validators=[Optional()])
    due_time = TimeField('Due Time', validators=[Optional()])
    assigned_to = SelectField('Assign To', coerce=int, validators=[Optional()])
    submit = SubmitField('Save Task')
