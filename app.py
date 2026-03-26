from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import os

from models import db, User, Professor, Student, Course, Session, Attendance, Setting, CourseGroup

app = Flask(__name__)
app.config['SECRET_KEY'] = 'iscae-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///iscae_presence.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email déjà utilisé')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(
            email=email,
            password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        if role == 'professor':
            professor = Professor(user_id=new_user.id)
            db.session.add(professor)
        elif role == 'student':
            student = Student(
                user_id=new_user.id,
                filiere=request.form.get('filiere', ''),
                niveau=request.form.get('niveau', ''),
                semestre=request.form.get('semestre', ''),
                groupe=request.form.get('groupe', ''),
                student_id=request.form.get('student_id', '')
            )
            db.session.add(student)
        
        db.session.commit()
        
        flash('Compte créé avec succès!')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Bienvenue {user.first_name}!')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'professor':
                return redirect(url_for('professor_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Email ou mot de passe incorrect')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnecté')
    return redirect(url_for('index'))

@app.route('/professor/dashboard')
@login_required
def professor_dashboard():
    if current_user.role != 'professor':
        return redirect(url_for('index'))
    
    professor = Professor.query.filter_by(user_id=current_user.id).first()
    courses = Course.query.filter_by(professor_id=professor.id).all()
    
    return render_template('professor/dashboard.html', courses=courses)

@app.route('/professor/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    if current_user.role != 'professor':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            professor = Professor.query.filter_by(user_id=current_user.id).first()
            
            name = request.form.get('name')
            code = request.form.get('code')
            nb_sessions = int(request.form.get('nb_sessions', 10))
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            start_time = datetime.strptime(request.form.get('start_time', '08:00'), '%H:%M').time()
            end_time = datetime.strptime(request.form.get('end_time', '10:00'), '%H:%M').time()
            
            # Créer la matière
            new_course = Course(
                name=name,
                code=code,
                professor_id=professor.id
            )
            db.session.add(new_course)
            db.session.flush()
            
            # Ajouter les groupes
            selected_groups = request.form.getlist('groups')
            for group_data in selected_groups:
                parts = group_data.split('|')
                if len(parts) == 4:
                    niveau, semestre, groupe, filiere = parts
                    course_group = CourseGroup(
                        course_id=new_course.id,
                        niveau=niveau,
                        semestre=semestre,
                        groupe=groupe if groupe else '',
                        filiere=filiere if filiere else ''
                    )
                    db.session.add(course_group)
            
            # Créer les séances
            for i in range(nb_sessions):
                session_date = start_date + timedelta(weeks=i)
                session = Session(
                    course_id=new_course.id,
                    session_number=i + 1,
                    date=session_date.date(),
                    start_time=start_time,
                    end_time=end_time,
                    is_active=False
                )
                db.session.add(session)
            
            db.session.commit()
            flash(f'Matière "{name}" créée avec {nb_sessions} séances!')
            return redirect(url_for('professor_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}')
            return redirect(url_for('create_course'))
    
    return render_template('professor/create_course.html')

@app.route('/professor/create_session/<int:course_id>', methods=['POST'])
@login_required
def create_session(course_id):
    if current_user.role != 'professor':
        return jsonify({'error': 'Non autorisé'}), 403
    
    now = datetime.now()
    end_time = (now + timedelta(hours=2)).time()
    
    new_session = Session(
        course_id=course_id,
        date=now.date(),
        start_time=now.time(),
        end_time=end_time,
        session_number=1
    )
    
    secret = new_session.generate_qr_secret()
    db.session.add(new_session)
    db.session.commit()
    
    qr_data = url_for('scan_qr', session_id=new_session.id, secret=secret, _external=True)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'success': True,
        'qr_code': img_str,
        'expiry': new_session.qr_expiry.isoformat()
    })

@app.route('/scan/<int:session_id>/<secret>')
def scan_qr(session_id, secret):
    session = Session.query.get_or_404(session_id)
    
    if not session.is_qr_valid() or session.qr_secret != secret:
        return "<h2>QR code invalide ou expiré</h2>", 400
    
    if current_user.is_authenticated and current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.id).first()
        
        existing = Attendance.query.filter_by(
            student_id=student.id,
            session_id=session_id
        ).first()
        
        if not existing:
            attendance = Attendance(
                student_id=student.id,
                session_id=session_id,
                status='present'
            )
            db.session.add(attendance)
            db.session.commit()
            return "<h2>✅ Présence enregistrée !</h2>"
        else:
            return "<h2>⚠️ Vous avez déjà enregistré votre présence</h2>"
    
    return "<h2>🔐 Veuillez vous connecter avec votre compte étudiant</h2>"

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    courses = Course.query.filter_by(
        filiere=student.filiere,
        niveau=student.niveau,
        semestre=student.semestre,
        groupe=student.groupe
    ).all()
    
    return render_template('student/dashboard.html', courses=courses)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    stats = {
        'students': Student.query.count(),
        'professors': Professor.query.count(),
        'courses': Course.query.count()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(role='admin').first():
            admin = User(
                email='admin@groupeiscae.ma',
                password=generate_password_hash('admin123'),
                first_name='Admin',
                last_name='ISCAE',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("=" * 50)
            print("Admin créé: admin@groupeiscae.ma / admin123")
            print("=" * 50)
        
        if not Setting.query.filter_by(key='absence_threshold').first():
            db.session.add(Setting(key='absence_threshold', value='3'))
            db.session.add(Setting(key='allowed_domains', value='groupeiscae.ma'))
            db.session.commit()
    
    app.run(debug=True)