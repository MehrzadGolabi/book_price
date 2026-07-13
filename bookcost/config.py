import os
import configparser

from bookcost.resources import app_dir


def get_db_config():
    """Reads database and security config from config.ini next to the app."""
    default_config = {
        'filename': 'book_publishing.db',
        'delete_password': 'admin'
    }

    config_path = os.path.join(app_dir(), 'config.ini')

    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        if 'database' in config:
            if 'filename' in config['database']:
                default_config['filename'] = config['database']['filename']
        if 'security' in config:
            if 'delete_password' in config['security']:
                default_config['delete_password'] = config['security']['delete_password']

    # Anchor a relative db filename at the app directory, not the process cwd —
    # otherwise launching from another folder silently opens a new empty db.
    if not os.path.isabs(default_config['filename']):
        default_config['filename'] = os.path.join(app_dir(), default_config['filename'])

    return default_config


DB_CONFIG = get_db_config()
