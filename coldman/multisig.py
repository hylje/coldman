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

    if argv[2] == "init":
        conf.init(db_name)
        sys.exit(0)
    else:
        conf.configure(db_name)

    try:
        actions[argv[2]](*argv[3:])
    finally:
        conf.db.close()

@conf.require
def addpub(key, *remarks):
    index = get_i()
    if index != 1:
        print "It is not possible to add new public keys after some "
        print "funds have been frozen. Please create a new data file, "
        print "add (and omit) public keys to it, and migrate funds to it." 
        sys.exit(2)
        
    key = pycoin.wallet.Wallet.from_wallet_key(key)

    remark = u" ".join(remarks)
    cursor = conf.db.cursor()
    cursor.execute(
        "INSERT INTO coldman_pubkeys (key, remark) VALUES (?, ?)", (
            key.wallet_key(as_private=False), 
            remark))
    conf.db.commit()

def genkey():
    """Generates a new deterministic private key using pycoin."""
    print "Please enter a seed that will act as the master secret."
    print "Leave empty to use a generated seed."
    secret_phrase = raw_input("Please enter the seed: ")
    random_phrase = False

    if not secret_phrase.strip():
        import os
        secret_phrase = os.urandom(512)
        random_phrase = True

    wallet = pycoin.wallet.Wallet.from_master_secret(secret_phrase)
    print "Private key"
    print wallet.wallet_key(as_private=True)
    print "-"*78
    print "Public key"
    print wallet.wallet_key(as_private=False)
    print "-"*78
    print "Save the private part in a secure location and don't tell"
    print "it to anybody."
    if not random_phrase: 
        print "You can also save the secret phrase, as"
        print "the same key can be generated from that as well."

@conf.require
def freeze(amount):
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
    ms = _get_wallets()

    if len(ms) > 1:
        n = len(ms)/2 + 1
        addr = _make_multisig_addr(ms, n)
    elif len(ms) == 1:
        addr = _make_normal_addr(ms[0])
    else:
        print "Datafile has no public keys."
        sys.exit(5)
    
    print "Would send %s to %s." % (amount, addr)
    #conf.bitcoind.sendtoaddress(addr, amount)
    
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
           "genkey": genkey,
           "init": conf.init}

@conf.require
def _report_addresses(irange):
    ms = _get_wallets()
    n = len(ms)/2 + 1

    for i in irange:
        try:
            ms_i = [m.subkey(i).wallet_key(as_private=False) for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            continue
        addr = conf.bitcoind.addmultisigaddress(n, ms_i)
        yield addr

@conf.require
def _make_multisig_addr(ms, n):

    i = get_i()
    ms_i = []
    while not ms_i:
        try:
            ms_i = [m.subkey(i).wallet_key(as_private=False) for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            i += 1
            
    addr = conf.bitcoind.addmultisigaddress(n, ms_i)

    save_i(i)

    return addr

@conf.require
def _make_normal_addr(wallet):
    return wallet.bitcoin_address()

@conf.require
def _get_wallets():
    cursor = conf.db.cursor()
    cursor.execute("SELECT key FROM coldman_pubkeys")
    wallet_keys = cursor.fetchall()
    return [pycoin.wallet.Wallet.from_wallet_key(key) 
            for key, in wallet_keys]

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
