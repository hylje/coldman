import sys, os.path

import sqlite3
import functools

import coldman.bitcoind
import coldman.binfo

db = None
bitcoind = None
binfo = None
settings = None
configured = False

def configure(db_name):
    """Loads the given datafile and configures the app using it.
    
    The datafile has to exist, as created by init below.
    """

    global db, bitcoind, binfo, settings, configured

    if not os.path.exists(db_name):
        print "No valid datafile given. Abort."
        sys.exit(3)

    db = sqlite3.connect(db_name)
    settings = _get_settings()
    bitcoind = coldman.bitcoind.BitcoindConnection(settings.btcd_conn)
    binfo = coldman.binfo.BinfoConnection(settings.binfo_conn)
    configured = True

def _get_settings():
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM coldman_settings")
    class Settings(object): 
        _dict = dict(cursor.fetchall())
        def __getattr__(self, key):
            return self._dict[key]
    return Settings()

class ImproperlyConfigured(Exception):
    pass

def require(f):
    @functools.wraps(f)
    def required(*args, **kwargs):
        if not configured:
            raise ImproperlyConfigured("Using this function requires that coldman.conf.configure has been successfully called.")
        return f(*args, **kwargs)
    return required

def init(db_name):
    """Creates a new datafile."""

    global db

    db = sqlite3.connect(db_name)

    print "The app saves the hot wallet RPC address in the data file."
    print "It is used to initiate transfers to cold wallet addresses, "
    print "please be aware of its security."
    btcd_conn = raw_input("Please enter the hot wallet RPC address: ")

    cursor = db.cursor()

    cursor.execute("""
CREATE TABLE coldman_settings (
id integer primary key,
key text,
value text)
""")

    # Commonly used versions of SQLite don't do multiple inserts
    cursor.execute("""
INSERT INTO coldman_settings (key, value) VALUES 
('index', '1')
""")
    cursor.execute("""
INSERT INTO coldman_settings (key, value) VALUES
('binfo_conn', 'http://blockchain.info/')
""")
    cursor.execute("""
INSERT INTO coldman_settings (key, value) VALUES
('btcd_conn', ?)
""", (btcd_conn,))
    
    cursor.execute("""
CREATE TABLE coldman_pubkeys (
id integer primary key,
key text,
remark text)
""")
    
    cursor.commit()

    db.close()

    print "Done. You can now add any public keys using addpub."
