import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()


def _sanitise_dsn(dsn: str) -> str:
    """Strip query parameters psycopg2 does not understand (e.g. channel_binding)."""
    if not dsn:
        return dsn
    parsed = urllib.parse.urlparse(dsn)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    params.pop('channel_binding', None)
    new_query = urllib.parse.urlencode({k: v[0] for k, v in params.items()})
    return parsed._replace(query=new_query).geturl()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    DATABASE_URL = _sanitise_dsn(os.environ.get('DATABASE_URL'))
    DB_POOL_MIN_CONN = 0
    DB_POOL_MAX_CONN = 10


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
