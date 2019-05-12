"""
__init__.py file. Part of the Contextualise project.

March 4, 2019
Brett Alistair Kromkamp (brett.kromkamp@gmail.com)
"""

import configparser
import os

from flask import Flask
from flask import render_template
from flask_mail import Mail
from flask_security import Security, SQLAlchemySessionUserDatastore, user_registered

from contextualise.security import user_store, user_models
from contextualise.utilities import filters

SETTINGS_FILE_PATH = os.path.join(os.path.dirname(__file__), '../settings.ini')

config = configparser.ConfigParser()
config.read(SETTINGS_FILE_PATH)

database_username = config['DATABASE']['Username']
database_password = config['DATABASE']['Password']
database_name = config['DATABASE']['Database']
email_username = config['EMAIL']['Username']
email_password = config['EMAIL']['Password']
email_server = config['EMAIL']['Server']
email_sender = config['EMAIL']['Sender']


# Application factory function
def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DEBUG=False,
        # TODO: Replace in production 'secrets.token_hex()'
        SECRET_KEY='6d67cace9a6e4525e2b945191ad8f1d4702c3186ea914ca80db86adb258bd850',
        TOPIC_STORE_USER=database_username,
        TOPIC_STORE_PASSWORD=database_password,
        TOPIC_STORE_DBNAME=database_name,
        SECURITY_PASSWORD_SALT='fff78df7dffdb745be561d9d8075c69ce6a6b4a8c8bce17377601a66fed72542',
        SECURITY_REGISTERABLE=True,
        SECURITY_RECOVERABLE=True,
        SECURITY_CHANGEABLE=True,
        SECURITY_EMAIL_SENDER=email_sender,
        SECURITY_URL_PREFIX='/auth',
        SECURITY_POST_LOGIN_VIEW='/maps',
        MAIL_SERVER=email_server,
        MAIL_PORT=587,
        MAIL_USE_SSL=False,
        MAIL_USERNAME=email_username,
        MAIL_PASSWORD=email_password,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024  # 2 megabytes
    )
    mail = Mail(app)

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/health')
    def hello():
        return 'Healthy!'

    # HTTP error handlers
    def forbidden(e):
        return render_template('403.html'), 403

    app.register_error_handler(403, forbidden)

    def page_not_found(e):
        return render_template('404.html'), 404

    app.register_error_handler(404, page_not_found)

    def internal_server_error(e):
        return render_template('500.html'), 500

    app.register_error_handler(500, internal_server_error)

    # Setup Flask-Security
    user_datastore = SQLAlchemySessionUserDatastore(user_store.db_session, user_models.User, user_models.Role)
    security = Security(app, user_datastore)

    @user_registered.connect_via(app)
    def user_registered_handler(app, user, confirm_token):
        default_role = user_datastore.find_role("user")
        user_datastore.add_role_to_user(user, default_role)
        user_store.db_session.commit()

    @app.before_first_request
    def create_user():
        user_store.init_db()

        # Create roles
        user_datastore.find_or_create_role(name='admin', description='Administrator')
        user_datastore.find_or_create_role(name='user', description='End user')

        # Create users
        if not user_datastore.get_user('admin@contextualise.io'):
            user_datastore.create_user(email='admin@contextualise.io', password="Passw0rd1")
        if not user_datastore.get_user('user@contextualise.io'):
            user_datastore.create_user(email='user@contextualise.io', password="Passw0rd1")
        if not user_datastore.get_user('multi@contextualise.io'):
            user_datastore.create_user(email='multi@contextualise.io', password="Passw0rd1")

        user_store.db_session.commit()

        # Assign roles
        user_datastore.add_role_to_user('user@contextualise.io', 'user')
        user_datastore.add_role_to_user('admin@contextualise.io', 'admin')

        user_datastore.add_role_to_user('multi@contextualise.io', 'user')
        user_datastore.add_role_to_user('multi@contextualise.io', 'admin')

        user_store.db_session.commit()

    @app.teardown_request
    def checkin_db(exc):
        user_store.db_session.remove()

    # Register custom filters
    filters.register_filters(app)

    # Register Blueprints
    from contextualise import api
    app.register_blueprint(api.bp)

    from contextualise import map
    app.register_blueprint(map.bp)

    from contextualise import topic
    app.register_blueprint(topic.bp)

    from contextualise import image
    app.register_blueprint(image.bp)

    from contextualise import link
    app.register_blueprint(link.bp)

    from contextualise import video
    app.register_blueprint(video.bp)

    from contextualise import association
    app.register_blueprint(association.bp)

    from contextualise import visualisation
    app.register_blueprint(visualisation.bp)

    # Add topic store
    from contextualise import topic_store
    topic_store.init_app(app)

    return app


# For debugging purposes (inside PyCharm)
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, use_debugger=False, use_reloader=False, passthrough_errors=True, host='0.0.0.0')