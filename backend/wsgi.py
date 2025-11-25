from backend.app import create_app

# WSGI application object for gunicorn
app = create_app()

# Optional: expose 'application' alias
application = app
