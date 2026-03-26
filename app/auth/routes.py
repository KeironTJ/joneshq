from collections import defaultdict, deque
from datetime import datetime, timedelta

from app import db, limiter
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User, UserRoles, Family, FamilyMembers, SiteSetting
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_user, logout_user 
import sqlalchemy as sa 
from urllib.parse import urlsplit
from app.auth import bp
from app.family_manager.helper import create_or_join_family

FAILED_ATTEMPT_WINDOW = timedelta(minutes=10)
FAILED_ATTEMPT_THRESHOLD = 5
_failed_attempts = {
    'login': defaultdict(deque),
    'register': defaultdict(deque),
}


def _client_identifier() -> str:
    forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    return forwarded_for or request.remote_addr or 'unknown'


def _record_auth_failure(kind: str, identifier: str) -> None:
    now = datetime.utcnow()
    attempts = _failed_attempts[kind][identifier]
    attempts.append(now)
    while attempts and now - attempts[0] > FAILED_ATTEMPT_WINDOW:
        attempts.popleft()
    if attempts and len(attempts) % FAILED_ATTEMPT_THRESHOLD == 0:
        current_app.logger.warning(
            "Repeated %s failures from %s (%s attempts in the last %s)",
            kind,
            identifier,
            len(attempts),
            FAILED_ATTEMPT_WINDOW,
        )

## Authentication Routes
### The login view function
@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"], error_message="Too many login attempts. Please try again later.")
def login():

    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()

    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            _record_auth_failure('login', _client_identifier())
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')

        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    elif form.is_submitted():
        _record_auth_failure('login', _client_identifier())
    
    return render_template('auth/login.html', 
                           title='Sign In', 
                           form=form)


@bp.route('/logout')
def logout():

    logout_user()

    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=["POST"], error_message="Too many registrations from this IP. Please try again later.")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if not SiteSetting.get_bool('allow_registration', default=current_app.config.get('ALLOW_REGISTRATION', False)):
        flash('Self-service signups are currently disabled.')
        return redirect(url_for('auth.login'))
    
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')

        # Assign the user to the default role (user)
        user_role = UserRoles(user_id=user.id, role_id=2)
        db.session.add(user_role)
        db.session.commit()
        flash('You have been assigned the default user role.')

        # Handle family creation or joining
        create_or_join = form.create_or_join.data
        family_name = form.family_name.data if create_or_join == 'create' else None
        invitation_code = form.invitation_code.data if create_or_join == 'join' else None

        if create_or_join_family(user, create_or_join, family_name, invitation_code):
            login_user(user)
            return redirect(url_for('main.dashboard'))

        _record_auth_failure('register', _client_identifier())
        # If family creation/joining fails, redirect back to registration
        return redirect(url_for('auth.register'))
    elif form.is_submitted():
        _record_auth_failure('register', _client_identifier())

    return render_template('auth/register.html', 
                           title='Register', 
                           form=form)