from sqlalchemy import Integer, String, func, DateTime, Time, Boolean
from datetime import datetime, timezone
import sqlalchemy.orm as so 
from flask_login import UserMixin 
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
import uuid


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


## USER MANAGEMENT
class User(UserMixin, db.Model):
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(64), index=True, unique=True)
    email = db.Column(String(120), index=True, unique=True)
    password_hash = db.Column(String(256))

    first_name = db.Column(String(64), nullable=True)  
    last_name = db.Column(String(64), nullable=True)  
    primary_phone_number = db.Column(String(20), nullable=True) 
    secondary_phone_number = db.Column(String(20), nullable=True)  
    dob = db.Column(DateTime, nullable=True)
    profile_picture = db.Column(String(256), nullable=True)  #TODO: Add URL or path to the profile picture 
    active_family_id = db.Column(Integer, db.ForeignKey('family.id'), nullable=True) 

    #Relationships
    roles = so.relationship('Role', secondary='user_roles', back_populates='users')
    address = so.relationship('Address', back_populates='user', uselist=False)  # One-to-one relationship with Address
    families = so.relationship('Family', secondary='family_members', back_populates='members')
    family_members = so.relationship('FamilyMembers', back_populates='user', overlaps='families')
    
    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return 'admin' in [role.name for role in self.roles]
    
    def assign_user_role(self, role_name):
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role and role not in self.roles:
            self.roles.append(role)
            return True 
        return False
    
    def unassign_user_role(self, role_name):
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role and role in self.roles:
            self.roles.remove(role)  
            return True
        return False
    
    def get_active_family(self):
        if self.active_family_id:
            return Family.query.get(self.active_family_id)
        return None

    def set_active_family(self, family_id):
        family = Family.query.get(family_id)
        if family and family in self.families:
            self.active_family_id = family_id
            return True
        return False
    
    def is_family_owner(self, family):
        return family.owner_id == self.id

    def is_family_co_owner(self, family):
        family_member = FamilyMembers.query.filter_by(user_id=self.id, family_id=family.id).first()
        return family_member and family_member.role_in_family == 'co-owner'

    def is_family_member_of(self, family):
        return family in self.families
    
# Model for addresses
class Address(db.Model):
    id = db.Column(Integer, primary_key=True)
    street_address = db.Column(String(255))
    city = db.Column(String(100))
    county = db.Column(String(100), nullable=True)  # Optional field
    postal_code = db.Column(String(20))
    country = db.Column(String(100), default='United Kingdom')  # Example default

    user_id = db.Column(Integer, db.ForeignKey('user.id'))
    user = so.relationship("User", back_populates="address")

    def __repr__(self):
        return f'<Address: {self.street_address}, {self.city}, {self.postal_code}>'
    


## ROLE MANAGEMENT
class Role(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(64), index=True, unique=True)

    # Relationships
    users = so.relationship('User', secondary='user_roles', back_populates='roles')
    
    def __repr__(self):
        return '<Role {}>'.format(self.name)
    

class UserRoles(db.Model):
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, db.ForeignKey('user.id'))
    role_id = db.Column(Integer, db.ForeignKey('role.id'), default=2)

## FAMILY MANAGEMENT
class Family(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(128), index=True, unique=True, nullable=False)
    owner_id = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(DateTime, default=func.now())
    invitation_code = db.Column(String(64), unique=True, nullable=False)  # New field

    # Relationships
    owner = so.relationship('User', backref='owned_families', foreign_keys=[owner_id])
    members = so.relationship('User', secondary='family_members', back_populates='families')
    family_members = so.relationship('FamilyMembers', back_populates='family', overlaps='members')
    

    def __repr__(self):
        return f'<Family {self.name}>'
    
    def generate_invitation_code(self):
        """Generate a unique invitation code for this family."""
        self.invitation_code = str(uuid.uuid4())

    def __init__(self, name, owner_id):
        """Ensure an invitation code is always set upon initialization."""
        self.name = name
        self.owner_id = owner_id
        self.generate_invitation_code()




# Association Table for Family Members
class FamilyMembers(db.Model):
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    family_id = db.Column(Integer, db.ForeignKey('family.id'), nullable=False)
    role_in_family = db.Column(String(64), default='member')  # e.g., 'owner', 'co-owner', 'member'

    # Relationships
    family = so.relationship("Family", backref="family_associations", overlaps="members")
    user = so.relationship("User", backref="user_associations", overlaps="families")

    # Define unique constraint to prevent duplicate user-family entries
    __table_args__ = (db.UniqueConstraint('user_id', 'family_id', name='_user_family_uc'),)

## MESSAGING
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key to User table
    content = db.Column(db.String(500), nullable=False)  
    timestamp = db.Column(db.DateTime, default=func.now(), nullable=False)
    deleted = db.Column(db.Boolean, default=False) 
    
    # Relationships
    user = db.relationship('User', backref='messages', lazy=True)  # Relationship to fetch User data


## MEAL PLANNING    
class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # KEEP AS REFERENCE - MAY LINK TO A FAMILY ID IN THE FUTURE
    meal_date = db.Column(db.DateTime, default=func.now(), nullable=False)
    meal_title = db.Column(db.String(64),default="", nullable=False)
    meal_description = db.Column(db.String(500)) 
    meal_source = db.Column(db.String(500)) 

    # Relationships
    user = db.relationship('User', backref='meal_plans', lazy=True) 


## ACTIVITY PLANNING
class ActivityPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # KEEP AS REFERENCE - MAY LINK TO A FAMILY ID IN THE FUTURE
    activity_date = db.Column(db.DateTime, default=func.now())
    activity_start_date = db.Column(db.DateTime, default=func.now(), nullable=False)
    activity_end_date = db.Column(db.DateTime, default=func.now(), nullable=False)
    activity_title = db.Column(db.String(64), nullable=False)
    activity_all_day_event = db.Column(db.Boolean, default=True)
    activity_start_time = db.Column(db.Time)
    activity_end_time = db.Column(db.Time)
    activity_description = db.Column(db.String(500)) 
    activity_location = db.Column(db.String(500)) 
    activity_comments = db.Column(db.String(500))

    # Relationships
    user = db.relationship('User', backref='activity_plans', lazy=True)


## CHORES
class Chore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(500))
    points = db.Column(db.Integer, default=0)
    due_date = db.Column(db.Date, nullable=True)
    recurring = db.Column(db.String(20), default='none')  # none, daily, weekly, monthly
    status = db.Column(db.String(20), default='pending')  # pending, awaiting_approval, completed
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=func.now())

    family = db.relationship('Family', backref='chores')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_chores')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_chores')
    completer = db.relationship('User', foreign_keys=[completed_by])


## ACHIEVEMENTS
class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    awarded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(500))
    icon = db.Column(db.String(50), default='fa-trophy')  # Font Awesome icon class
    points = db.Column(db.Integer, default=0)
    date_earned = db.Column(db.DateTime, default=func.now())

    family = db.relationship('Family', backref='achievements')
    user = db.relationship('User', foreign_keys=[user_id], backref='achievements')
    awarder = db.relationship('User', foreign_keys=[awarded_by])


## REWARDS
class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(500))
    points_cost = db.Column(db.Integer, nullable=False)
    icon = db.Column(db.String(50), default='fa-gift')
    available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())

    family = db.relationship('Family', backref='rewards')
    creator = db.relationship('User', foreign_keys=[created_by])


class RewardRedemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reward_id = db.Column(db.Integer, db.ForeignKey('reward.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points_spent = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='approved')  # pending, approved, rejected
    redeemed_at = db.Column(db.DateTime, default=func.now())

    reward = db.relationship('Reward', backref='redemptions')
    user = db.relationship('User', foreign_keys=[user_id], backref='redemptions')


## BEHAVIOUR TRACKING
class BehaviourEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 star rating
    notes = db.Column(db.String(500))
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=func.now())

    family = db.relationship('Family', backref='behaviour_entries')
    user = db.relationship('User', foreign_keys=[user_id], backref='behaviour_entries')
    recorder = db.relationship('User', foreign_keys=[recorded_by])


## POINTS LEDGER
class PointsLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)  # positive = earned, negative = spent
    source_type = db.Column(db.String(30), nullable=False)  # chore, achievement, behaviour, redemption
    source_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=func.now())

    family = db.relationship('Family', backref='points_ledger')
    user = db.relationship('User', foreign_keys=[user_id], backref='points_ledger')


## HEALTH TRACKING
class HealthCategory(db.Model):
    """User-customisable health tracking categories with goals."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key = db.Column(db.String(30), nullable=False)  # slug e.g. 'exercise', 'driving'
    label = db.Column(db.String(64), nullable=False)  # display name
    unit = db.Column(db.String(20), nullable=False)  # min, L, hrs, lbs, /5, steps, etc
    icon = db.Column(db.String(50), default='fa-circle')
    color = db.Column(db.String(20), default='#6C757D')
    aggregation = db.Column(db.String(10), default='sum')  # 'sum' or 'latest'
    daily_goal = db.Column(db.Float, nullable=True)  # target per day (null = no goal)
    sort_order = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())

    user = db.relationship('User', backref='health_categories')
    __table_args__ = (db.UniqueConstraint('user_id', 'key', name='_user_category_uc'),)


class HealthLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=func.now())

    user = db.relationship('User', backref='health_logs')


## TO-DO LISTS
class TodoList(db.Model):
    """A named to-do list owned by a user, optionally shared with a family."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=True)
    title = db.Column(db.String(128), nullable=False, default='My List')
    color = db.Column(db.String(20), default='#3A8F85')
    icon = db.Column(db.String(50), default='fa-list-check')
    created_at = db.Column(db.DateTime, default=func.now())

    owner = db.relationship('User', backref='todo_lists')
    family = db.relationship('Family', backref='todo_lists')
    items = db.relationship('TodoItem', backref='todo_list', lazy='dynamic',
                            cascade='all, delete-orphan',
                            order_by='TodoItem.sort_order, TodoItem.created_at')


class TodoItem(db.Model):
    """A single to-do item within a list."""
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('todo_list.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    notes = db.Column(db.String(1000))
    priority = db.Column(db.String(10), default='medium')  # low, medium, high, urgent
    due_date = db.Column(db.Date, nullable=True)
    due_time = db.Column(db.Time, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=func.now())

    creator = db.relationship('User', foreign_keys=[user_id], backref='created_todos')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_todos')
    completer = db.relationship('User', foreign_keys=[completed_by])


## SITE SETTINGS
class SiteSetting(db.Model):
    """Key-value store for site-wide configuration flags."""
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=False, default='')
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now())

    @staticmethod
    def get(key, default=None):
        row = db.session.get(SiteSetting, key)
        return row.value if row else default

    @staticmethod
    def get_bool(key, default=False):
        val = SiteSetting.get(key)
        if val is None:
            return default
        return val.lower() in ('1', 'true', 'yes', 'on')

    @staticmethod
    def set(key, value):
        row = db.session.get(SiteSetting, key)
        if row:
            row.value = str(value)
        else:
            row = SiteSetting(key=key, value=str(value))
            db.session.add(row)
        db.session.commit()


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    read = db.Column(db.Boolean, default=False)


class SiteBanner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, default='Site Notice')
    message = db.Column(db.String(500), nullable=False, default='')
    banner_type = db.Column(db.String(20), nullable=False, default='info')  # info, warning, success, danger
    is_active = db.Column(db.Boolean, default=False)
    show_on_index = db.Column(db.Boolean, default=True)
    show_on_all_pages = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=func.now())
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)