import os
import subprocess
import sys
import time

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import User


@click.command("create-admin")
@click.option("--email", prompt="Admin email", help="Email for the admin user.")
@click.option(
    "--password",
    prompt="Admin password",
    hide_input=True,
    confirmation_prompt=True,
    help="Password for the admin user.",
)
@with_appcontext
def create_admin_command(email, password):
    """Create or update an admin user."""
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.role = "admin"
        user.password_hash = generate_password_hash(password)
        user.is_active = True
        click.echo(f"Updated existing admin user: {email}")
    else:
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
            is_active=True,
        )
        db.session.add(user)
        click.echo(f"Created admin user: {email}")

    db.session.commit()


@click.command("seed")
@click.option(
    "--scenario",
    default="basic",
    show_default=True,
    type=click.Choice(["basic", "scaled", "comprehensive", "complex", "learning", "quiz"]),
    help="Seed scenario to run.",
)
@click.option("--size", default="100", show_default=True, help="Dataset size for scaled seed scenarios.")
@click.option("--key", default=None, help="Seed password, or set E16_SEED_PASSWORD.")
@with_appcontext
def seed_command(scenario, size, key):
    """Run development seed data scripts from scripts/."""
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
    if app_env == "production":
        click.echo("ERROR: seeding is blocked when APP_ENV=production.", err=True)
        sys.exit(1)

    if key:
        os.environ["E16_SEED_PASSWORD"] = key
    elif not os.getenv("E16_SEED_PASSWORD"):
        os.environ["E16_SEED_PASSWORD"] = "demo-password"

    script_map = {
        ("basic", "100"): "seed_100.py",
        ("basic", "300"): "seed_300_users.py",
        ("scaled", "100"): "seed_scenarios.py",
        ("scaled", "300"): "seed_scenarios_scaled.py",
        ("comprehensive", None): "seed_all_comprehensive.py",
        ("complex", None): "seed_complex_data.py",
        ("learning", None): "seed_learning_logs.py",
        ("quiz", None): "seed_quizzes_assignments.py",
    }
    script_file = script_map.get((scenario, size)) or script_map.get((scenario, None))
    if not script_file:
        available = ", ".join(sorted({item[0] for item in script_map}))
        raise click.ClickException(f"Unsupported seed combination. Available scenarios: {available}")

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    script_path = os.path.join(repo_root, "scripts", script_file)
    if not os.path.exists(script_path):
        raise click.ClickException(f"Seed script not found: {script_path}")

    click.echo(f"Running seed scenario '{scenario}' with {script_file}")
    result = subprocess.run([sys.executable, script_path], cwd=repo_root, check=False)
    if result.returncode != 0:
        raise click.ClickException(f"Seed script failed with exit code {result.returncode}")

    click.echo("Seeding completed.")


@click.command("check-deadlines")
@with_appcontext
def check_deadlines_command():
    """Scan upcoming deadlines and send reminder notifications."""
    from .services.deadline_reminder import check_and_notify_deadlines

    count = check_and_notify_deadlines()
    click.echo(f"Deadline check complete. {count} notification(s) processed.")


@click.command("run-jobs")
@click.option("--interval", default=5, type=int, help="Polling interval in seconds.")
@with_appcontext
def run_jobs_command(interval):
    """Run dedicated background job worker loop (production mode)."""
    from flask import current_app
    from .services.jobs import run_pending_jobs
    
    click.echo(f"Starting E16 LMS background worker (polling every {interval}s)...")
    app = current_app._get_current_object()
    
    try:
        while True:
            run_pending_jobs(app)
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("Worker stopped by user.")

@click.command("create-hoc-vu")
@click.option("--email", prompt="Học vụ email", help="Email for the Học vụ user.")
@click.option(
    "--password",
    prompt="Học vụ password",
    hide_input=True,
    confirmation_prompt=True,
    help="Password for the Học vụ user.",
)
@with_appcontext
def create_hoc_vu_command(email, password):
    """Create or update a Học vụ (Academic Affairs) user."""
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.role = "hoc_vu"
        user.password_hash = generate_password_hash(password)
        user.is_active = True
        user.must_change_password = False
        click.echo(f"Updated existing user to hoc_vu: {email}")
    else:
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role="hoc_vu",
            is_active=True,
            must_change_password=False,
        )
        db.session.add(user)
        click.echo(f"Created hoc_vu user: {email}")

    db.session.commit()


@click.command("create-teacher")
@click.option("--email", prompt="Teacher email", help="Email for the teacher user.")
@click.option(
    "--password",
    prompt="Teacher password",
    hide_input=True,
    confirmation_prompt=True,
    help="Password for the teacher user.",
)
@with_appcontext
def create_teacher_command(email, password):
    """Create or update a Teacher user."""
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.role = "teacher"
        user.password_hash = generate_password_hash(password)
        user.is_active = True
        user.must_change_password = False
        click.echo(f"Updated existing user to teacher: {email}")
    else:
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role="teacher",
            is_active=True,
            must_change_password=False,
        )
        db.session.add(user)
        click.echo(f"Created teacher user: {email}")

    db.session.commit()


@click.command("create-student")
@click.option("--email", prompt="Student email", help="Email for the student user.")
@click.option(
    "--password",
    prompt="Student password",
    hide_input=True,
    confirmation_prompt=True,
    help="Password for the student user.",
)
@with_appcontext
def create_student_command(email, password):
    """Create or update a Student user."""
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.role = "student"
        user.password_hash = generate_password_hash(password)
        user.is_active = True
        user.must_change_password = False
        click.echo(f"Updated existing user to student: {email}")
    else:
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role="student",
            is_active=True,
            must_change_password=False,
        )
        db.session.add(user)
        click.echo(f"Created student user: {email}")

    db.session.commit()


@click.command("auto-transition-courses")
@with_appcontext
def auto_transition_courses_command():
    """Auto-transition courses based on starts_at/ends_at dates."""
    from .services.course_lifecycle import auto_transition_courses

    changed = auto_transition_courses()
    click.echo(f"Auto-transition complete. {changed} course(s) transitioned.")


def init_app(app):
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_command)
    app.cli.add_command(check_deadlines_command)
    app.cli.add_command(run_jobs_command)
    app.cli.add_command(create_hoc_vu_command)
    app.cli.add_command(create_teacher_command)
    app.cli.add_command(create_student_command)
    app.cli.add_command(auto_transition_courses_command)
