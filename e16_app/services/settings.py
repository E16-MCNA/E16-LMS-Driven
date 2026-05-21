from ..extensions import db
from ..models import SystemSetting

_settings_cache = {}

def get_setting(key, default=None):
    """
    Retrieves a system setting from DB with local caching.
    """
    global _settings_cache
    if key in _settings_cache:
        return _settings_cache[key]
        
    try:
        setting = db.session.query(SystemSetting).filter_by(key=key).first()
        if setting:
            _settings_cache[key] = setting.value
            return setting.value
    except Exception:
        pass
    return default

def flush_settings_cache():
    global _settings_cache
    _settings_cache = {}
