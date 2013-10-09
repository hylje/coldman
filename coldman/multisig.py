"""Initial implementation of a multisig cold wallet generator."""

import sys

import pycoin.wallet

from coldman import conf

def main(argv):
    if len(argv) < 2:
        print "Usage:"
        print "%s <datafile> [%s]" % (argv[0], "|".join(actions))
        print "To begin, use init to create a new datafile."
        sys.exit(1)

    db_name = argv[1]
    conf.configure(db_name)

    try:
        actions[argv[2]](*argv[3:])
    finally:
        conf.db.close()

@conf.require
def init():
    """Creates a new datafile."""

    print "The app saves the hot wallet RPC address in the data file."
    print "It is used to initiate transfers to cold wallet addresses, "
    print "please be aware of its security."
    btcd_conn = raw_input("Please enter the hot wallet RPC address: ")

    cursor = conf.db.cursor()
    
    cursor.execute("""
CREATE TABLE coldman_settings (
id integer primary key,
key text,
value text)
""")

    cursor.execute("""
INSERT INTO coldman_settings (key, value) VALUES 
('index', '1'),
('binfo_conn', 'http://blockchain.info/'),
('btcd_conn', %s),
""", (btcd_conn,))
    
    cursor.execute("""
CREATE TABLE coldman_pubkeys (
id integer primary key,
key text,
remark text)
""")

    print "Done. You can now add any public keys using addpub."

@conf.require
def addpub(key, *remarks):
    index = get_i()
    if index != 1:
        print "It is not possible to add new public keys after some "
        print "funds have been frozen. Please create a new data file, "
        print "add (and omit) public keys to it, and migrate funds to it." 
        sys.exit(2)
        
    remark = u" ".join(remarks)
    cursor = conf.db.cursor()
    cursor.execute("INSERT INTO coldman_pubkeys (key, remark) VALUES (%s, %s)", (key, remark))

@conf.require
def freeze(amount):
    ms = _get_wallets()
    n = len(ms)/2 + 1
    _freeze(amount, ms, n)

@conf.require
def report():
    """Finds all addresses by all known permutations of `ms` and gets
    their balances from Blockchain.info.
    """    
    irange = xrange(0, get_i())
    addrs = _report_addresses(irange)
    balances = binfo.multiaddr(active=addrs)
    
    print "Total %s addresses:" % len(balances["addresses"])
    for addr in balances["addresses"]:
        print u"%s: %s" % (addr["address"], addr["final_balance"])

actions = {"freeze": freeze, 
           "report": report, 
           "addpub": addpub, 
           "init": init}

@conf.require
def _report_addresses(irange):
    ms = _get_wallets()
    n = len(ms)/2 + 1

    for i in irange:
        try:
            ms_i = [m.subkey(i) for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            continue
        addr = conf.bitcoind.addmultisigaddress(n, ms_i)
        yield addr

@conf.require
def _freeze(amount, ms, n):
    """Freezes `amount` (decimal.Decimal) amount of funds from
    `wallet` (django_bitcoin.models.Wallet) to a new cold wallet
    identified by `ms` (pycoin.wallet.Wallet) public keys, of which
    `n` (int) are needed to withdraw.

    The `ms` are first derived into an (usually) unique index, so the
    resulting multi-sig address is fresh.

    The cold wallets can be thawed by creating an unsigned transaction
    that is then signed by at least `n` private key holders, then sent
    into the bitcoin network.
    """

    i = get_i()
    ms_i = []
    while not ms_i:
        try:
            ms_i = [m.subkey(i) for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            i += 1
            
    addr = conf.bitcoind.addmultisigaddress(n, ms_i)

    conf.bitcoind.sendtoaddress(addr, amount)

    save_i(i)

@conf.require
def _get_wallets():
    cursor = conf.db.cursor()
    cursor.execute("SELECT key FROM coldman_pubkeys")
    wallet_keys = cursor.fetchall()
    return [pycoin.wallet.Wallet(key) for key, in wallet_keys]

@conf.require
def get_i():
    cursor = conf.db.cursor()
    cursor.execute("SELECT value FROM coldman_settings WHERE key='index'")
    i, = cursor.fetchone()
    return int(i)

@conf.require
def save_i(i):
    cursor = conf.db.cursor()
    cursor.execute("UPDATE coldman_settings SET value=%s WHERE key='index'", (unicode(i),))

if __name__ == "__main__":
    main(sys.argv)
