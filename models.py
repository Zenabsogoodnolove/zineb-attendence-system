from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import random
import string

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    professor_details = db.relationship('Professor', backref='user', uselist=False)
    student_details = db.relationship('Student', backref='user', uselist=False)

class Professor(db.Model):
    __tablename__ = 'professors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    department = db.Column(db.String(100))
    
    courses = db.relationship('Course', backref='professor', lazy=True)

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    filiere = db.Column(db.String(50), default='')  # Pour M1 S4 et M2
    niveau = db.Column(db.String(20), nullable=False)  # PMA, M1, M2
    semestre = db.Column(db.String(10), nullable=False)  # S1, S2, S3, S4, S5, S6
    groupe = db.Column(db.String(10), default='')  # G1-G6 pour PMA et M1 S3
    student_id = db.Column(db.String(20), unique=True)
    
    attendances = db.relationship('Attendance', backref='student', lazy=True)

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True)
    filiere = db.Column(db.String(50), default='')  # Rendre optionnel
    niveau = db.Column(db.String(20), default='')   # Rendre optionnel
    semestre = db.Column(db.String(10), default='') # Rendre optionnel
    groupe = db.Column(db.String(10), default='')
    professor_id = db.Column(db.Integer, db.ForeignKey('professors.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    groups = db.relationship('CourseGroup', backref='course', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('Session', backref='course', lazy=True, cascade='all, delete-orphan')

class CourseGroup(db.Model):
    __tablename__ = 'course_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    niveau = db.Column(db.String(20), nullable=False)
    semestre = db.Column(db.String(10), nullable=False)
    groupe = db.Column(db.String(10), default='')
    filiere = db.Column(db.String(50), default='')
    
    __table_args__ = (db.UniqueConstraint('course_id', 'niveau', 'semestre', 'groupe', 'filiere', name='unique_course_group'),)

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    session_number = db.Column(db.Integer, nullable=False)  # <-- CETTE LIGNE DOIT EXISTER
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    qr_secret = db.Column(db.String(50))
    qr_expiry = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    attendances = db.relationship('Attendance', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def generate_qr_secret(self):
        chars = string.ascii_letters + string.digits
        self.qr_secret = ''.join(random.choice(chars) for _ in range(20))
        self.qr_expiry = datetime.utcnow() + timedelta(seconds=30)
        return self.qr_secret
    
    def is_qr_valid(self):
        return datetime.utcnow() < self.qr_expiry

class Attendance(db.Model):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    scan_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='present')
    
    __table_args__ = (db.UniqueConstraint('student_id', 'session_id', name='unique_attendance'),)

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(200))
    description = db.Column(db.String(200))
    
    @classmethod
    def get_absence_threshold(cls):
        setting = cls.query.filter_by(key='absence_threshold').first()
        return int(setting.value) if setting else 3
    
    @classmethod
    def get_allowed_domains(cls):
        setting = cls.query.filter_by(key='allowed_domains').first()
        if setting and setting.value:
            return setting.value.split(',')
        return ['groupeiscae.ma']