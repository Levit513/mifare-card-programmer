#!/usr/bin/env python3
"""
MIFARE Card Programming and Distribution System
Web application for creating, managing, and distributing MIFARE card programs
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, Length
import os
import json
import qrcode
import io
import base64
from datetime import datetime, timedelta
import secrets
import jwt
from mifare import CardReader, MifareUtils

app = Flask(__name__)

# Make datetime available in templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mifare_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
CORS(app)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    programs_received = db.relationship('ProgramDistribution', backref='user', lazy=True)

class CardProgram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sector_data = db.Column(db.Text, nullable=False)  # JSON string of sector data
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    distributions = db.relationship('ProgramDistribution', backref='program', lazy=True)

class ProgramDistribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('card_program.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_token = db.Column(db.String(200), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])

class CardProgramForm(FlaskForm):
    name = StringField('Program Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    sector_data = TextAreaField('Sector Data (JSON)', validators=[DataRequired()])

class DistributeForm(FlaskForm):
    program_id = SelectField('Card Program', coerce=int, validators=[DataRequired()])
    user_id = SelectField('User', coerce=int, validators=[DataRequired()])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        print(f"Login attempt for user: {form.username.data}")
        if user:
            print(f"User found: {user.username}, is_admin: {user.is_admin}")
            if check_password_hash(user.password_hash, form.password.data):
                print("Password verified successfully")
                login_user(user)
                return redirect(url_for('index'))
            else:
                print("Password verification failed")
        else:
            print("User not found")
        flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered')
            return render_template('register.html', form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    programs = CardProgram.query.filter_by(created_by=current_user.id).all()
    users = User.query.filter_by(is_admin=False).all()
    distributions = ProgramDistribution.query.join(CardProgram).filter(
        CardProgram.created_by == current_user.id
    ).all()
    
    return render_template('admin_dashboard.html', 
                         programs=programs, users=users, distributions=distributions)

@app.route('/user')
@login_required
def user_dashboard():
    distributions = ProgramDistribution.query.filter_by(user_id=current_user.id).all()
    return render_template('user_dashboard.html', distributions=distributions)

@app.route('/create_program', methods=['GET', 'POST'])
@login_required
def create_program():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    form = CardProgramForm()
    if form.validate_on_submit():
        try:
            # Validate JSON format
            json.loads(form.sector_data.data)
            
            program = CardProgram(
                name=form.name.data,
                description=form.description.data,
                sector_data=form.sector_data.data,
                created_by=current_user.id
            )
            db.session.add(program)
            db.session.commit()
            flash('Card program created successfully')
            return redirect(url_for('admin_dashboard'))
        except json.JSONDecodeError:
            flash('Invalid JSON format in sector data')
    
    return render_template('create_program.html', form=form)

@app.route('/distribute', methods=['GET', 'POST'])
@login_required
def distribute_program():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    form = DistributeForm()
    form.program_id.choices = [(p.id, p.name) for p in CardProgram.query.filter_by(created_by=current_user.id).all()]
    form.user_id.choices = [(u.id, u.username) for u in User.query.filter_by(is_admin=False).all()]
    
    if form.validate_on_submit():
        # Generate secure access token
        access_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)  # 24-hour expiry
        
        distribution = ProgramDistribution(
            program_id=form.program_id.data,
            user_id=form.user_id.data,
            access_token=access_token,
            expires_at=expires_at
        )
        db.session.add(distribution)
        db.session.commit()
        
        flash('Program distributed successfully')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('distribute.html', form=form)

@app.route('/program/<token>')
def receive_program(token):
    distribution = ProgramDistribution.query.filter_by(access_token=token).first()
    
    if not distribution:
        return render_template('error.html', message='Invalid or expired program link')
    
    if distribution.expires_at < datetime.utcnow():
        return render_template('error.html', message='Program link has expired')
    
    if distribution.is_used:
        return render_template('error.html', message='Program has already been used')
    
    program = distribution.program
    return render_template('receive_program.html', 
                         distribution=distribution, program=program)

@app.route('/api/program_data/<token>')
def get_program_data(token):
    distribution = ProgramDistribution.query.filter_by(access_token=token).first()
    
    if not distribution or distribution.expires_at < datetime.utcnow() or distribution.is_used:
        return jsonify({'error': 'Invalid or expired token'}), 403
    
    # Mark as used (one-time use)
    distribution.is_used = True
    distribution.used_at = datetime.utcnow()
    db.session.commit()
    
    program = distribution.program
    sector_data = json.loads(program.sector_data)
    
    return jsonify({
        'program_name': program.name,
        'sector_data': sector_data,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/scan_card')
@login_required
def scan_card():
    """API endpoint to scan for MIFARE cards"""
    try:
        reader = CardReader()
        cards = reader.scan_cards()
        return jsonify({'success': True, 'cards': cards})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/sector_editor')
@login_required
def sector_editor():
    """Interactive sector editor for MIFARE Classic cards"""
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    return render_template('sector_editor.html')

@app.route('/users')
@login_required
def manage_users():
    """User management page"""
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('manage_users.html', users=users)

@app.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    """Create new user"""
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('create_user.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('create_user.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=False
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User {username} created successfully')
        return redirect(url_for('manage_users'))
    
    return render_template('create_user.html')

def create_admin_user():
    """Create default admin user if none exists"""
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    if admin:
        # Update existing admin user with correct password
        admin.password_hash = generate_password_hash('admin123')
        admin.is_admin = True
        db.session.commit()
        print("Admin user updated: admin/admin123")
    else:
        # Create new admin user
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created: admin/admin123")
    
    # Verify the password works
    test_user = User.query.filter_by(username='admin').first()
    if test_user and check_password_hash(test_user.password_hash, 'admin123'):
        print("✅ Admin password verification successful")
    else:
        print("❌ Admin password verification failed")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
