import os
from datetime import date
from functools import wraps

import click
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="SET NULL"), unique=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    student = db.relationship("Student", backref=db.backref("account", uselist=False))

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return bool(self.active)


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    document_number = db.Column(db.String(30), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    birth_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    enrollments = db.relationship("Enrollment", backref="student", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    teacher_name = db.Column(db.String(120), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    enrollments = db.relationship("Enrollment", backref="course", cascade="all, delete-orphan")


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    academic_period = db.Column(db.String(30), nullable=False)
    enrolled_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    grade = db.relationship("Grade", backref="enrollment", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("student_id", "course_id", "academic_period", name="uq_enrollment"),)


class Grade(db.Model):
    __tablename__ = "grades"
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id", ondelete="CASCADE"), unique=True, nullable=False)
    grade = db.Column(db.Numeric(4, 2), nullable=False)
    observations = db.Column(db.String(255))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    database_url = os.getenv("DATABASE_URL", "sqlite:///aulagest_dev.db")

    if database_url.startswith("mysql://"):
        database_url = database_url.replace(
            "mysql://", "mysql+pymysql://", 1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "0") == "1"
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Inicia sesión para continuar."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and user.active and check_password_hash(user.password_hash, password):
                login_user(user)
                flash("Bienvenido a AulaGest.", "success")
                next_page = request.args.get("next", "")
                if next_page.startswith("/") and not next_page.startswith("//"):
                    return redirect(next_page)
                return redirect(url_for("dashboard"))
            flash("Usuario o contraseña incorrectos.", "danger")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Has cerrado sesión.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            stats = {
                "students": Student.query.count(),
                "courses": Course.query.count(),
                "enrollments": Enrollment.query.count(),
                "grades": Grade.query.count(),
            }
            recent = Enrollment.query.order_by(Enrollment.id.desc()).limit(5).all()
            return render_template("dashboard.html", stats=stats, recent=recent)
        enrollments = []
        if current_user.student_id:
            enrollments = Enrollment.query.filter_by(student_id=current_user.student_id).order_by(Enrollment.id.desc()).all()
        return render_template("dashboard.html", stats=None, recent=[], own_enrollments=enrollments)

    @app.route("/estudiantes")
    @admin_required
    def students():
        q = request.args.get("q", "").strip()
        query = Student.query
        if q:
            like = f"%{q}%"
            query = query.filter(db.or_(Student.first_name.like(like), Student.last_name.like(like),
                                        Student.document_number.like(like), Student.email.like(like)))
        return render_template("students.html", students=query.order_by(Student.last_name).all(), q=q)

    @app.route("/estudiantes/nuevo", methods=["GET", "POST"])
    @admin_required
    def student_new():
        if request.method == "POST":
            student = Student(
                document_number=request.form.get("document_number", "").strip(),
                first_name=request.form.get("first_name", "").strip(),
                last_name=request.form.get("last_name", "").strip(),
                email=request.form.get("email", "").strip().lower(),
                phone=request.form.get("phone", "").strip() or None,
                birth_date=parse_date(request.form.get("birth_date", "")),
            )
            if not all([student.document_number, student.first_name, student.last_name, student.email]):
                flash("Completa los campos obligatorios.", "danger")
            else:
                db.session.add(student)
                if save_or_flash("Estudiante creado correctamente."):
                    return redirect(url_for("students"))
        return render_template("student_form.html", student=None, title="Nuevo estudiante")

    @app.route("/estudiantes/<int:student_id>/editar", methods=["GET", "POST"])
    @admin_required
    def student_edit(student_id):
        student = db.get_or_404(Student, student_id)
        if request.method == "POST":
            student.document_number = request.form.get("document_number", "").strip()
            student.first_name = request.form.get("first_name", "").strip()
            student.last_name = request.form.get("last_name", "").strip()
            student.email = request.form.get("email", "").strip().lower()
            student.phone = request.form.get("phone", "").strip() or None
            student.birth_date = parse_date(request.form.get("birth_date", ""))
            if not all([student.document_number, student.first_name, student.last_name, student.email]):
                flash("Completa los campos obligatorios.", "danger")
            elif save_or_flash("Estudiante actualizado correctamente."):
                return redirect(url_for("students"))
        return render_template("student_form.html", student=student, title="Editar estudiante")

    @app.post("/estudiantes/<int:student_id>/eliminar")
    @admin_required
    def student_delete(student_id):
        student = db.get_or_404(Student, student_id)
        db.session.delete(student)
        if save_or_flash("Estudiante eliminado."):
            return redirect(url_for("students"))
        return redirect(url_for("students"))

    @app.route("/cursos")
    @login_required
    def courses():
        return render_template("courses.html", courses=Course.query.order_by(Course.name).all(),
                               can_manage=current_user.role == "admin")

    @app.route("/cursos/nuevo", methods=["GET", "POST"])
    @admin_required
    def course_new():
        if request.method == "POST":
            course = Course(code=request.form.get("code", "").strip().upper(),
                            name=request.form.get("name", "").strip(),
                            description=request.form.get("description", "").strip() or None,
                            teacher_name=request.form.get("teacher_name", "").strip(),
                            credits=parse_int(request.form.get("credits"), 3))
            if not all([course.code, course.name, course.teacher_name]) or not 1 <= course.credits <= 30:
                flash("Completa los campos obligatorios y usa créditos entre 1 y 30.", "danger")
            else:
                db.session.add(course)
                if save_or_flash("Curso creado correctamente."):
                    return redirect(url_for("courses"))
        return render_template("course_form.html", course=None, title="Nuevo curso")

    @app.route("/cursos/<int:course_id>/editar", methods=["GET", "POST"])
    @admin_required
    def course_edit(course_id):
        course = db.get_or_404(Course, course_id)
        if request.method == "POST":
            course.code = request.form.get("code", "").strip().upper()
            course.name = request.form.get("name", "").strip()
            course.description = request.form.get("description", "").strip() or None
            course.teacher_name = request.form.get("teacher_name", "").strip()
            course.credits = parse_int(request.form.get("credits"), 3)
            if not all([course.code, course.name, course.teacher_name]) or not 1 <= course.credits <= 30:
                flash("Completa los campos obligatorios y usa créditos entre 1 y 30.", "danger")
            elif save_or_flash("Curso actualizado correctamente."):
                return redirect(url_for("courses"))
        return render_template("course_form.html", course=course, title="Editar curso")

    @app.post("/cursos/<int:course_id>/eliminar")
    @admin_required
    def course_delete(course_id):
        course = db.get_or_404(Course, course_id)
        db.session.delete(course)
        if save_or_flash("Curso eliminado."):
            return redirect(url_for("courses"))
        return redirect(url_for("courses"))

    @app.route("/matriculas")
    @login_required
    def enrollments():
        if current_user.role == "admin":
            items = Enrollment.query.order_by(Enrollment.id.desc()).all()
        elif current_user.student_id:
            items = Enrollment.query.filter_by(student_id=current_user.student_id).order_by(Enrollment.id.desc()).all()
        else:
            items = []
        return render_template("enrollments.html", enrollments=items, can_manage=current_user.role == "admin",
                               students=Student.query.order_by(Student.last_name).all() if current_user.role == "admin" else [],
                               courses=Course.query.order_by(Course.name).all() if current_user.role == "admin" else [])

    @app.post("/matriculas/nueva")
    @admin_required
    def enrollment_new():
        student_id = parse_int(request.form.get("student_id"), 0)
        course_id = parse_int(request.form.get("course_id"), 0)
        period = request.form.get("academic_period", "").strip()
        if not Student.query.get(student_id) or not Course.query.get(course_id) or not period:
            flash("Selecciona un estudiante, un curso y el periodo académico.", "danger")
        else:
            db.session.add(Enrollment(student_id=student_id, course_id=course_id, academic_period=period))
            save_or_flash("Matrícula creada correctamente.")
        return redirect(url_for("enrollments"))

    @app.post("/matriculas/<int:enrollment_id>/eliminar")
    @admin_required
    def enrollment_delete(enrollment_id):
        item = db.get_or_404(Enrollment, enrollment_id)
        db.session.delete(item)
        if save_or_flash("Matrícula eliminada."):
            return redirect(url_for("enrollments"))
        return redirect(url_for("enrollments"))

    @app.route("/calificaciones", methods=["GET", "POST"])
    @login_required
    def grades():
        if current_user.role == "admin":
            if request.method == "POST":
                enrollment_id = parse_int(request.form.get("enrollment_id"), 0)
                value = request.form.get("grade", "").strip()
                observations = request.form.get("observations", "").strip() or None
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    score = -1
                enrollment = db.session.get(Enrollment, enrollment_id)
                if not enrollment or not 0 <= score <= 5:
                    flash("Selecciona una matrícula válida e ingresa una nota entre 0.00 y 5.00.", "danger")
                else:
                    record = Grade.query.filter_by(enrollment_id=enrollment_id).first()
                    if record:
                        record.grade, record.observations = round(score, 2), observations
                    else:
                        db.session.add(Grade(enrollment_id=enrollment_id, grade=round(score, 2), observations=observations))
                    if save_or_flash("Calificación guardada."):
                        return redirect(url_for("grades"))
            items = Grade.query.join(Enrollment).order_by(Grade.id.desc()).all()
            pending = Enrollment.query.outerjoin(Grade).filter(Grade.id.is_(None)).all()
            return render_template("grades.html", grades=items, pending=pending, can_manage=True)
        items = []
        if current_user.student_id:
            items = Grade.query.join(Enrollment).filter(Enrollment.student_id == current_user.student_id).order_by(Grade.id.desc()).all()
        return render_template("grades.html", grades=items, pending=[], can_manage=False)

    @app.route("/usuarios", methods=["GET", "POST"])
    @admin_required
    def users():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "user")
            student_id = parse_int(request.form.get("student_id"), 0) or None
            if len(username) < 3 or len(password) < 10 or role not in ("admin", "user"):
                flash("El usuario debe tener 3 caracteres y la contraseña al menos 10.", "danger")
            elif User.query.filter_by(username=username).first():
                flash("Ese nombre de usuario ya existe.", "danger")
            elif student_id and (not db.session.get(Student, student_id) or User.query.filter_by(student_id=student_id).first()):
                flash("El estudiante no existe o ya tiene una cuenta vinculada.", "danger")
            else:
                db.session.add(User(username=username, password_hash=generate_password_hash(password),
                                    role=role, student_id=student_id))
                if save_or_flash("Usuario creado correctamente."):
                    return redirect(url_for("users"))
        return render_template("users.html", users=User.query.order_by(User.username).all(),
                               students=Student.query.order_by(Student.last_name).all())

    @app.post("/usuarios/<int:user_id>/estado")
    @admin_required
    def user_toggle(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            flash("No puedes desactivar tu propia cuenta.", "warning")
        else:
            user.active = not user.active
            if save_or_flash("Estado de usuario actualizado."):
                return redirect(url_for("users"))
        return redirect(url_for("users"))

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="No tienes permisos para acceder a esta sección."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="No encontramos la página solicitada."), 404

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas. Para producción, preferir migraciones versionadas."""
        db.create_all()
        click.echo("Tablas creadas.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.password_option()
    def create_admin(username, password):
        """Crea una cuenta administrativa inicial."""
        if len(password) < 10:
            raise click.ClickException("La contraseña debe tener al menos 10 caracteres.")
        if User.query.filter_by(username=username).first():
            raise click.ClickException("Ese usuario ya existe.")
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role="admin"))
        db.session.commit()
        click.echo(f"Administrador '{username}' creado.")

    return app


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def save_or_flash(success_message):
    try:
        db.session.commit()
        flash(success_message, "success")
        return True
    except IntegrityError:
        db.session.rollback()
        flash("No se pudo guardar. Verifica que el documento, correo, código o matrícula no estén duplicados.", "danger")
        return False


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
