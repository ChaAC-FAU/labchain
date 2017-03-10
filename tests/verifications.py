from .utils import *
import traceback

errors = 0

def trans_test(fn):
    """ Immediately runs a test that requires a blockchain, and a transaction with private key in that blockchain. """

    gen_chain = Blockchain([GENESIS_BLOCK])
    assert gen_chain.verify_all()
    key = Signing.generate_private_key()
    reward_trans = Transaction([], [TransactionTarget(key, gen_chain.compute_blockreward(gen_chain.head))])
    chain = extend_blockchain(gen_chain, [reward_trans])
    try:
        fn(chain, reward_trans)
    except:
        global errors
        errors += 1
        traceback.print_exc()

@trans_test
def test_double_spend1(chain, reward_trans):
    trans1 = new_trans(reward_trans)
    chain = extend_blockchain(chain, [trans1])

    # spending the coin in reward_trans again must fail:
    extend_blockchain(chain, [trans1], verify_res=False)

    # spending the output of trans1 must work:
    assert chain.is_coin_still_valid(trans_as_input(trans1))

@trans_test
def test_double_spend2(chain, reward_trans):
    trans1 = new_trans(reward_trans)
    trans2 = new_trans(reward_trans)
    extend_blockchain(chain, [trans1, trans2], verify_res=False)

@trans_test
def test_double_spend3(chain, reward_trans):
    trans1 = Transaction([trans_as_input(reward_trans), trans_as_input(reward_trans)], [])
    key = reward_trans.targets[0].recipient_pk
    trans1.sign([key, key])
    extend_blockchain(chain, [trans1], verify_res=False)


OKGREEN = '\033[92m'
FAIL = '\033[91m'
ENDC = '\033[0m'
if errors == 0:
    print(OKGREEN + "All tests passed." + ENDC)
else:
    print(FAIL + str(errors) + " tests failed." + ENDC)
