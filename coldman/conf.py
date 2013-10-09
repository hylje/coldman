import sqlite3

import coldman.bitcoind
import coldman.binfo

db = None
bitcoind = None
binfo = None
settings = None
configured = False

def configure(db_name):
    """Loads the given datafile and configures the app using it."""

    global db, bitcoind, binfo, settings, configured

    db = sqlite3.connect(db_name)
    settings = _get_settings()
    bitcoind = coldman.bitcoind.BitcoindConnection(settings.btcd_conn)
    binfo = coldman.binfo.BinfoConnection(settings.binfo_conn)
    configured = True

def _get_settings():
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM coldman_settings")
    return dict(cursor.fetchall())

class ImproperlyConfigured(Exception):
    pass

def require(f):
    @functools.wraps(f)
    def required(*args, **kwargs):
        if not configured:
            raise ImproperlyConfigured("Using this function requires that coldman.conf.configure has been successfully called.")
        return f(*args, **kwargs)
    return required
