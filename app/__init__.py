import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables from .env file (optional but recommended)
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # --- Configuration ---
    # Use environment variable for SECRET_KEY in production for security.
    # Provide a default for development convenience.
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_dev_secret_key')

    # Ensure the instance folder exists (where SQLite DB will be stored)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Database configuration (SQLite in the instance folder)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'database.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable modification tracking

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)  # Initialize Flask-Migrate

    with app.app_context():
        # Import parts of our application
        from . import routes
        from . import models # Import models to ensure they are known to SQLAlchemy

        # Register Blueprints
        app.register_blueprint(routes.main_bp)

        return app