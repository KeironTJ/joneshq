from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional, Length
from wtforms.fields import TelField
from wtforms.widgets import Input


class ContactForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired()])
    email = StringField('Your Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')


class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[Optional()])
    last_name = StringField('Last Name', validators=[Optional()])
    primary_phone_number = TelField('Primary Phone Number', validators=[Optional()])
    secondary_phone_number = TelField('Secondary Phone Number', validators=[Optional()])
    # For simplicity, we'll handle address in a separate form/view for now
    dob = DateField('Date of Birth', validators=[Optional()])
    submit = SubmitField('Update Profile')