Coldman
=======

Coldman is a tool for a multi-signature, deterministic wallet (BIP
0032) based cold wallet. It bases heavily on pycoin and bitcoind.

Coldman is usable with some manual work to fill the gaps. 

Coldtool is a command-line interface.

Why use
-------

It's the ultimate solution for a communal cold wallet -- all dressed
in tinfoil hattery!

If you can trust your comrades, you just use a shared private key.


Creating a Cold Wallet
----------------------

First, create a coldman datafile using `coldtool data.cm init`. You
will be asked necessary information about running the cold wallet,
including the hot wallet that will be drained.

After the datafile is built, you can add as many BIP 0032 formatted
public keys as you like. Bitcoin itself supports up to 20 multisig
public keys. Add all keys before making the first transaction: it is
not possible to alter the set of public keys after the first
transaction is made.


Stashing Bitcoin Away
---------------------

Use `coldtool data.cm freeze <amount>`. A single-use multisig address
is created and the hot wallet is drained immediately.

If you're not expecting to use your coins for a while, you can save
the following chapters until then. It's this easy!


Spending Bitcoin from the Cold Wallet
-------------------------------------

First pick which cold wallet address to drain using `coldtool data.cm
report`. Take note of the `i` value of the address you wish to drain.

Now you can create the unsigned transaction using `coldtool data.cm
thaw i` using the value of `i` that you picked. By default the
transaction will return money to the hot wallet configured for the
datafile, but you can specify another address as well.

The printed transaction is not complete, and you need to get it signed
with private keys until the multisig requirement is fulfilled.


How to get the Spending Transaction Signed
------------------------------------------

You can do this step on an offline machine. It is in fact recommended
you manage private keys on an offline computer that you communicate
transactions to using a thumb drive.

You need to know the raw transaction generated above, the `i` of the
original transaction to spend and the original (deterministic) private
key corresponding to a public key added to the datafile. The private
key should be in BIP 0032 deterministic key format. Unfortunately the
method to get such formatted key from Electrum or other wallets is
left as an exercise to the reader.

First derive the zeroth subkey (the default account). Then
derive the zeroth subkey from the default account, coming up with the
external chain. Finally, you derive the external chain with `i`. Take
note of the resulting private key.

If your wallet software doesn't provide low-level key derivation
functions, you can use `coldtool data.cm derive wif k` to get the `k`th
subkey of the given key. Coldtool doesn't actually need a data file in
this case, but it's there for syntax reasons. 

Anyway, now that you have the fully derived private key, you can sign
it using Bitcoind or Electrum:

`bitcoind signrawtransaction <hex part of the raw transaction above> '["<derived private key>`"]'

OR

`electrum signrawtransaction <hex part of the raw transaction above> '<input_info part of the raw transaction above>' '["<derived private key>"]'`

Note that the input_info is a JSON object and the private key is
inside a JSON array.

You are returned a new raw transaction at the `hex` part and
indication whether the transaction is sendable in the `complete`
part. If `complete` is `false`, repeat this step with different
private keys.


Spending the Signed Transaction
-------------------------------

On an online Bitcoind or Electrum, use `sendrawtransaction`:

`bitcoind sendrawtransaction <hex part of a complete transaction>`

OR 

`electrum sendrawtransaction <hex part of a complete transaction>`

Wait for the transaction to confirm, and enjoy your newly thawed
bitcoins.


Improving 
---------

Please see the Github issue tracker (https://github.com/hylje/coldman/issues)