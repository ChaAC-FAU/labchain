#! /usr/bin/env/python3
import hashlib
import logging
from .crypto import *
from binascii import hexlify, unhexlify
from datetime import datetime
from .transaction import *

global transaction
global prog_stack
global validity
global control_flow_stack
global alt_stack

#The actual interpreter for our scriptlanguage
def interpreter(inputscript: str, outputscript: str, tx):

    global transaction
    #get nLockTime from transaction for OP_CHECKLOCKTIME / OP_CHECKLOCKTIMEVERIFY / OP_NOP2
    transaction = tx

    #parse script-strings to LabScript
    scriptSig = LabScript(inputscript + " " + outputscript)
    #scriptPubKey = LabScript(outputscript)
    
    #create Scriptstack
    stack = LabStack()

    #execute scripts and merge the results
    return scriptSig.execute_script(stack)
    #return scriptPubKey.execute_script(stack)

def invalidate():
    """
    Makes the script invalid. 
    """
    global validity
    validity = False

class LabStack:
    """
    Labscript uses a stack for imperative control flow. LabStack is a simple 
    implementation of a stack. The LabStack is used by the LabScript 
    interpreter to store intermediate values. A newly initialized LabStack is
    always empty. 
    """

    def __init__(self):
        self.items = []    
        self.sp = 0
        return  

    def is_empty(self):
        """
        Tests whether the stack is empty and returns true if yes, false 
        otherwise.
        """
        return self.sp == 0

    def size(self):
        """
        Returns the number of items currently in the stack.
        """
        return self.sp

    def peek(self):
        """
        Returns the item at the top of the stack without removing it from the
        stack. If the stack is empty, None is returned.
        """
        if self.is_empty():
            return None
        
        return self.items[self.sp-1]

    def push(self, item):
        """
        Appends a new item to the top of the stack and increases the stack 
        pointer by 1.
        """
        self.items.append(item)
        self.sp += 1
        return

    def pop(self):
        """
        Removes the item at the top of the stack and returns it and the stack
        pointer is decreased by 1. If the stack is empty, None is returned.
        """
        if self.is_empty():
            return None
        
        self.sp -= 1
        return self.items.pop()

    def set_sp(pos):
        """
        Sets the stack pointer to pos and alters the stack accordingly:
        If pos is greater than the current sp, the stack is made bigger and
        the new items are initialized with None. If pos is less than the 
        current sp, the stack is made smaller and all items above the current
        sp are simply removed from the stack.
        """
        while(sp != pos):
            if pos > self.sp:
                self.push(None)
            else:
                self.pop()
        return   

    def print_stack(self):
        """
        Prints all items on the stack, from top to bottom.
        """
        for i in self.items[::-1]:
            print(str(i))
        return

    
class LabScript:
    """
    LabScript is a simple imperative stack-based script language. This class
    implements a script as a List of commands to be executed from left to
    right. The items in the list of commands can be any data or an operation.

    USAGE:
    The constructor is called using a string that represents the script. 
    This string is a long chain consisting of commands, which are arbitrary
    substrings, each separated by a whitespace. If a command substring matches
    an opcode string, as specified in the OPLIST below, the interpreter will
    parse opcode into an operation and execute its behavior. Any other command
    will be simply pushed onto the stack as data.
    """

    """
    Following is an overview  of all implemented operations sorted after area
    of application.
    For more information go to https://en.bitcoin.it/wiki/Script
    or read the explanation within the op-implementation below:

        Constants:

            OP_0
            OP_FALSE
            OP_1NEGATE
            OP_1
            OP_TRUE

        Flow Control:

            OP_NOP
            OP_IF
            OP_NOTIF
            OP_ELSE
            OP_ENDIF
            OP_VERIFY
            OP_RETURN

        Stack:

            OP_TOALTSTACK
            OP_FROMALTSTACK
            OP_IFDUP
            OP_DROP
            OP_DUP
            OP_NIP
            OP_OVER
            OP_PICK
            OP_ROLL
            OP_ROT
            OP_SWAP
            OP_TUCK
            OP_2DROP
            OP_2DUP
            OP_3DUP
            OP_2OVER
            OP_2ROT
            OP_2SWAP

        Splice:

            -

        Bitwise logic:

            OP_INVERT
            OP_AND
            OP_OR
            OP_XOR
            OP_EQUAL
            OP_EQUALVERIFY

        Arithmetic:

            OP_1ADD
            OP_1SUB
            OP_2MUL
            OP_2DIV
            OP_NOT
            OP_0NOTEQUAL
            OP_ADD
            OP_SUB
            OP_MUL
            OP_DIV
            OP_MOD
            OP_BOOLAND
            OP_BOOLOR
            OP_NUMEQUAL
            OP_NUMEQUALVERIFY
            OP_NUMNOTEQUAL
            OP_LESSTHAN
            OP_GREATERTHAN
            OP_LESSTHANOREQUAL
            OP_GREATERTHANOREQUAL
            OP_MIN
            OP_MAX
            OP_WITHIN

        Crypto:

            OP_RIPDEM160
            OP_SHA1
            OP_SHA256
            OP_HASH160
            OP_HASH256
            OP_CHECKSIG
            OP_CHECKSIGVERIFY
            #OP_CHECKMULTISIG ???
            #OP_CHECKMULTISIGVERIFY ???

        Locktime:

            OP_CHECKLOCKTIME
            OP_CHECKLOCKTIMEVERIFY
            OP_NOP2

        Reserved words:

            OP_NOP1
            OP_NOP4
            OP_NOP5
            OP_NOP6
            OP_NOP7
            OP_NOP8
            OP_NOP9
            OP_NOP10
    """

    def __init__(self, list_of_commands: str):
        self.prog_queue = list_of_commands.split()
        self.pc = 1 # program counter
        self.pend = len(self.prog_queue) # end of program

        self.valid = True # is the script valid? if not, better not use it
                            # for anything important.

        self.if_endif_syntax_check()
        return


    def to_string(self):
        schtring_aeeh_string = ""
        for i in self.prog_queue:
            schtring_aeeh_string+=str(i)+" "

        schtring_aeeh_string = schtring_aeeh_string[:-1]
        return schtring_aeeh_string 



    # operation implementations

    def op_ripemd160():
        #The input is hashed using RIPEMD160.
        #DONE

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(str(prog_stack.pop()).encode('utf-8'))
        ripemd160 = hexlify(ripemd160.digest())
        prog_stack.push(ripemd160.decode('utf-8'))
        return

    def op_sha1():
        #The input is hashed using SHA-1.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        sha1 = hashlib.sha1()
        sha1.update(str(prog_stack.pop()).encode('utf-8'))
        sha1 = hexlify(sha1.digest())
        prog_stack.push(sha1.decode('utf-8'))
        return
    def op_sha256():
        #The input is hashed using SHA-256.
        #DONE

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        sha256 = hashlib.sha256()
        sha256.update(str(prog_stack.pop()).encode('utf-8'))
        sha256 = hexlify(sha256.digest())
        prog_stack.push(sha256.decode('utf-8'))
        return

    def op_hash256():
        #The input is hashed two times with SHA-256.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        sha256 = hashlib.sha256()
        sha256.update(str(prog_stack.pop()).encode('utf-8'))
        sha256 = hexlify(sha256.digest())
        prog_stack.push(sha256.decode('utf-8'))

        sha256 = hashlib.sha256()
        sha256.update(str(prog_stack.pop()).encode('utf-8'))
        sha256 = hexlify(sha256.digest())
        prog_stack.push(sha256.decode('utf-8'))
        return

    def op_hash160():
        #The input is hashed twice: first with SHA-256 and then with
        # RIPEMD-160.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        sha256 = hashlib.sha256()
        sha256.update(str(prog_stack.pop()).encode('utf-8'))
        sha256 = hexlify(sha256.digest())
        prog_stack.push(sha256.decode('utf-8'))

        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(str(prog_stack.pop()).encode('utf-8'))
        ripemd160 = hexlify(ripemd160.digest())
        prog_stack.push(ripemd160.decode('utf-8'))
        return

    def op_checksig():
        # The signature used by OP_CHECKSIG must be a valid signature for
        # this hash and public key.
        #If it is, 1 is returned, 0 otherwise.

        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            prog_stack.push(str(0))
            return

        pubKey = Key.from_json_compatible(prog_stack.pop())

        tx_hash = transaction.get_hash()

        sig = unhexlify(prog_stack.pop())

        if pubKey.verify_sign(tx_hash, sig):
            prog_stack.push(str(1))
            return

        logging.warning("Signature not verified")
        prog_stack.push(str(0))
        return

    def op_checksigverify():
        #runs checksig and verify afterwards
        
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            prog_stack.push(str(0))
            return

        mystring = "-----BEGIN PUBLIC KEY-----" + prog_stack.pop() + "-----END PUBLIC KEY-----"
        pubKey = bytes(mystring, 'utf-8')
        sig = unhexlify(prog_stack.pop())
        #sig = bytes(prog_stack.pop(), 'utf-8')

        signing_service = Key(pubKey)

        hash = transaction.get_hash()

        #verify signature
        if signing_service.verify_sign(hash, sig):
            prog_stack.push(str(1))
            return

        logging.warning("Signature not verified")
        prog_stack.push(str(0))

        #verify
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        if(not(int(prog_stack.pop()))):
            logging.warning('Transaction not valid!')
            invalidate()
        return
        

    def op_nop():
        #Does nothing
        #DONE
        pass
        return

    def op_equal():
        #Returns 1 if the inputs are exactly equal, 0 otherwise.
        #DONE
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop() 
        x2 = prog_stack.pop()
        
        if(x1 == x2):
            prog_stack.push(str(1))
        else:
            prog_stack.push(str(0))

        return

    def op_verify():
        #Marks transaction as invalid if top stack value is not true. The
        # top stack value is removed.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        if(not(int(prog_stack.pop()))):
            logging.warning('Transaction not valid!')
            invalidate()
        return

    def op_if():
        #DONE
        # If the top stack value is not False, the statements are executed.
        # The top stack value is removed. 

            # this operation pushes a new conditional flag onto the
            # control flow stack according to this scheme:
            #
            # control_flow_stack, prog_stack:   push flag
            # -----------------------------------------------
            # ALLOW_ALL, TRUE:      push ALLOW_ALL
            # ALLOW_ALL, FALSE:     push ALLOW_IF_ELSE
            #
            # ALLOW_IF_ELSE, TRUE:  push ALLOW_IF
            # ALLOW_IF_ELSE, FALSE: push ALLOW_IF
            #
            # ALLOW_IF, TRUE:       push ALLOW_IF
            # ALLOW_IF, FALSE:      push ALLOW_IF 

        ALLOW_ALL=0 # Any operation can be executed.
        ALLOW_IF_ELSE=1 # Nothing but ifs, elses and endifs can be executed.
        ALLOW_IF=2  # Nothing but ifs and endifs can be executed. 

        flag = control_flow_stack.peek()

        if flag == ALLOW_ALL:

            if(prog_stack.is_empty()):
                logging.warning("Stack is empty")
                invalidate()
                return

            if int(prog_stack.pop()):
                control_flow_stack.push(ALLOW_ALL)
            else: 
                control_flow_stack.push(ALLOW_IF_ELSE)
        else:
            control_flow_stack.push(ALLOW_IF)

        return

    def op_notif():
        #DONE
        # If the top stack value is False, the statements are executed.
        # The top stack value is removed. 

            # this operation pushes a new conditional flag onto the
            # control flow stack. Any operations that follow are only 
            # executed if the current flag is True. 

        ALLOW_ALL=0 # Any operation can be executed.
        ALLOW_IF_ELSE=1 # Nothing but ifs, elses and endifs can be executed.
        ALLOW_IF=2  # Nothing but ifs and endifs can be executed.

        flag = control_flow_stack.peek()

        if flag == ALLOW_ALL:

            if(prog_stack.is_empty()):
                logging.warning("Not enough arguments")
                invalidate()
                return

            if int(prog_stack.pop()):
                control_flow_stack.push(ALLOW_IF_ELSE)
            else:
                control_flow_stack.push(ALLOW_ALL)
        else:
            control_flow_stack.push(ALLOW_IF)
        
        return

    def op_else():
        #DONE
        # If the preceding OP_IF or OP_NOTIF or OP_ELSE was not executed
        # then these statements are and if the preceding OP_IF or OP_NOTIF
        # or OP_ELSE was executed then these statements are not. 

            # this operation changes the current conditional flag onto the
            # control flow stack according to this scheme:
            #
            # control_flow_stack, prog_stack:   push flag
            # -----------------------------------------------
            # ALLOW_ALL     -> ALLOW_IF_ELSE    
            # ALLOW_IF_ELSE -> ALLOW_ALL
            # if the flag is ALLOW_IF, this is never executed.

        ALLOW_ALL=0 # Any operation can be executed.
        ALLOW_IF_ELSE=1 # Nothing but ifs, elses and endifs can be executed.
        ALLOW_IF=2  # Nothing but ifs and endifs can be executed.

        flag = control_flow_stack.pop()
        if flag == ALLOW_ALL:
            control_flow_stack.push(ALLOW_IF_ELSE)
        if flag == ALLOW_IF_ELSE:
            control_flow_stack.push(ALLOW_ALL)

        return

    def op_endif():
        #DONE
        # Ends an if/else block.
        control_flow_stack.pop()
        return

    def op_return():

        """Marks transaction as invalid.
        A standard way of attaching extra data to transactions is to add a zero-value output with a
        scriptPubKey consisting of OP_RETURN followed by exactly one pushdata op. Such outputs are
        provably unspendable, reducing their cost to the network.
        Currently it is usually considered non-standard (though valid) for a transaction to have more
        than one OP_RETURN output or an OP_RETURN output with more than one pushdata op. """

        #DONE
        prog_stack.push(str(0))
        logging.warning('Transaction not valid!')
        invalidate()
        return           

    def op_dup():
        #Duplicates the top stack item.
        #DONE

        if(prog_stack.peek()!=None):
            prog_stack.push(prog_stack.peek())
            return

        logging.warning("Stack is empty")
        invalidate()
        return

    def op_drop():
        #Removes the top stack item.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is already empty")
            invalidate()
            return

        prog_stack.pop()
        return

    def op_checklocktime():

        global transaction

        #Error Indicator
        errno = 0

        #Error if Stack is empty
        if(prog_stack.is_empty() or prog_stack.size() < 2):
            errno = 1


        #if top stack item is greater than the transactions nLockTime field ERROR
        temp = float(prog_stack.pop())
        try:
            timestamp = datetime.fromtimestamp(temp)
        except TypeError:
            logging.error("A timestamp needs to be supplied after the OP_CHECKLOCKTIME operation!")
            invalidate()
            return

        #TODO we need to make sure that the timezones are being taken care of
        if(timestamp > datetime.utcnow()):
            print("You need to wait at least " + str(timestamp - datetime.utcnow()) + " to spend this Tx")
            errno = 3

        if(errno):
            #errno = 1 Stack is empty
            if(errno == 1):
                logging.warning('Stack is empty!')
                invalidate()
                return

            #errno = 2 Top-Stack-Value < 0
            if(errno == 2):
                logging.warning('Top-Stack-Value < 0')
                invalidate()
                return

            #errno = 3 top stack item is greater than the transactions
            if(errno == 3):
                #logging.warning('you need to wait more to unlock the funds!')
                invalidate()
                return
        return

    def op_equalverify():
        #Same as OP_EQUAL, but runs OP_VERIFY afterward.
        #DONE
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop() 
        x2 = prog_stack.pop()
        
        if(x1 == x2):
            prog_stack.push(str(1))
        else:
            prog_stack.push(str(0))

        #verify
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        if(not(int(prog_stack.pop()))):
            logging.warning('Transaction not valid!')
            invalidate()
        return

    def op_invert():
        #Flips all of the bits in the input. disabled at BITCOIN.
        #DONE
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        prog_stack.push(str(~ int(prog_stack.pop())))
        return

    def op_and():
        #Boolean and between each bit in the inputs. disabled at BITCOIN.
        #DONE
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x2 = int(prog_stack.pop())

        prog_stack.push(str(x1 & x2))

        return

    def op_or():
        #Boolean or between each bit in the inputs. disabled at BITCOIN.
        #DONE
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x2 = int(prog_stack.pop())

        prog_stack.push(str(x1 | x2))

        return

    def op_xor():
        #Boolean exclusive or between each bit in the inputs. disabled at BITCOIN.
        #DONE
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x2 = int(prog_stack.pop())

        prog_stack.push(str(x1 ^ x2))

        return

    def op_true():
        #op_1()
        #The number 1 is pushed onto the stack. 
        #DONE
        prog_stack.push(str(1))
        return

    def op_false():
        #op_0()
        #The number 0 is pushed onto the stack.
        #DONE
        prog_stack.push(str(0))
        return

    def op_1negate():
        #The number -1 is pushed onto the stack.
        #DONE
        prog_stack.push(str(-1))
        return

    def op_toaltstack():
        #Puts the input onto the top of the alt stack.
        #Removes it from the main stack.
        #DONE

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return


        alt_stack.push(prog_stack.pop())
        return

    def op_fromaltstack():
        #Puts the input onto the top of the main stack.
        #Removes it from the alt stack.
        #DONE

        if(alt_stack.is_empty()):
            logging.warning("Alt_stack is empty")
            invalidate()
            return

        prog_stack.push(alt_stack.pop())
        return

    def op_ifdup():
        #If the top stack value is not 0, duplicate it.
        #DONE

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        if(int(prog_stack.peek()) != 0):
            op_dup()

        return

    def op_nip():
        #Removes the second-to-top stack item.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        prog_stack.pop()
        prog_stack.push(x1)

        return

    def op_over():
        #Copies the second-to-top stack item to the top.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.peek()
        prog_stack.push(x1)
        prog_stack.push(x2)
        return

    def op_pick():
        #The item n back in the stack is copied to the top.

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        n = int(prog_stack.pop())

        if(prog_stack.size() < n):
            logging.warning("Not enough arguments")
            invalidate()
            return

        stack_list = list()

        for i in range(n):
            stack_list.append(prog_stack.pop())

        for i in range(n):
            prog_stack.push(stack_list[n - 1 - i])

        prog_stack.push(stack_list[n-1])

        return

    def op_roll():
        #The item n back in the stack is moved to the top.

        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        n = int(prog_stack.pop())

        if(prog_stack.size() < n):
            logging.warning("Not enough arguments")
            invalidate()
            return

        stack_list = list()

        for i in range(n):
            stack_list.append(prog_stack.pop())

        for i in range (n-1):
            prog_stack.push(stack_list[n - 2 - i])

        prog_stack.push(stack_list[n-1])

        return

    def op_rot():
        #The top three items on the stack are rotated to the left.

        if(prog_stack.size() < 3):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        x3 = prog_stack.pop()
        
        prog_stack.push(x1)
        prog_stack.push(x3)
        prog_stack.push(x2)

        return

    def op_swap():
        #The top two items on the stack are swapped.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        
        prog_stack.push(x1)
        prog_stack.push(x2)

        return

    def op_tuck():
        #The item at the top of the stack is copied
        #and inserted before the second-to-top item.
        #like cuddling :3 OwO
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        
        prog_stack.push(x1)
        prog_stack.push(x2)
        prog_stack.push(x1)

        return

    def op_2drop():
        #Removes the top two stack items.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        prog_stack.pop()
        prog_stack.pop()
        return

    def op_2dup():
        #Duplicates the top two stack items.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        
        prog_stack.push(x2)
        prog_stack.push(x1)
        prog_stack.push(x2)
        prog_stack.push(x1)

        return

    def op_3dup():
        #Duplicates the top three stack items.
        if(prog_stack.size() < 3):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        x3 = prog_stack.pop()
        
        prog_stack.push(x3)
        prog_stack.push(x2)
        prog_stack.push(x1)
        prog_stack.push(x3)
        prog_stack.push(x2)
        prog_stack.push(x1)

        return

    def op_2over():
        #Copies the pair of items two spaces back in the stack to the front.
        if(prog_stack.size() < 4):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        x3 = prog_stack.pop()
        x4 = prog_stack.pop()
        
        prog_stack.push(x2)
        prog_stack.push(x1)
        prog_stack.push(x4)
        prog_stack.push(x3)
        prog_stack.push(x2)
        prog_stack.push(x1)

        return

    def op_2rot():
        #The fifth and sixth items back are moved to the top of the stack.
        if(prog_stack.size() < 6):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        x3 = prog_stack.pop()
        x4 = prog_stack.pop()
        x5 = prog_stack.pop()
        x6 = prog_stack.pop()
        
        prog_stack.push(x2)
        prog_stack.push(x1)
        prog_stack.push(x6)
        prog_stack.push(x5)
        prog_stack.push(x4)
        prog_stack.push(x3)

        return

    def op_2swap():
        #Swaps the top two pairs of items.
        if(prog_stack.size() < 4):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x1 = prog_stack.pop()
        x2 = prog_stack.pop()
        x3 = prog_stack.pop()
        x4 = prog_stack.pop()
        
        prog_stack.push(x2)
        prog_stack.push(x1)
        prog_stack.push(x4)
        prog_stack.push(x3)

        return

    def op_1add():
        #1 is added to the input.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x1 += 1
        prog_stack.push(str(x1))
        return

    def op_1sub():
        #1 is subtracted from the input.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x1 -= 1
        prog_stack.push(str(x1))
        return

    def op_2mul():
        #The input is multiplied by 2. disabled at BITCOIN.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x1 *= 2
        prog_stack.push(str(x1))
        return

    def op_2div():
        #The input is divided by 2. disabled at BITCOIN.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        x1 /= 2
        prog_stack.push(str(x1))
        return

    def op_not():
        #If the input is 0 or 1, it is flipped. Otherwise the output will be 0.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        
        if(x1 == 0):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_0notequal():
        #Returns 0 if the input is 0. 1 otherwise.
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        x1 = int(prog_stack.pop())
        
        if(x1 == 0):
            prog_stack.push(str(0))
            return

        prog_stack.push(str(1))
        return

    def op_add():
        #a is added to b.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        prog_stack.push(str(a + b))
        return

    def op_sub():
        #b is subtracted from a.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        prog_stack.push(str(a - b))
        return

    def op_mul():
        #a is multiplied by b. disabled at BITCOIN.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        prog_stack.push(str(a * b))
        return

    def op_div():
        #a is divided by b. disabled at BITCOIN.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        prog_stack.push(str(a / b))
        return

    def op_mod():
        #Returns the remainder after dividing a by b. disabled at BITCOIN.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        prog_stack.push(str(a % b))
        return

    def op_booland():
        #If both a and b are not "" (null string), the output is 1. Otherwise 0.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = prog_stack.pop()
        b = prog_stack.pop()

        if(a != "" and b != ""):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_boolor():
        #If a or b is not "" (null string), the output is 1. Otherwise 0.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = prog_stack.pop()
        b = prog_stack.pop()

        if(a != "" or b != ""):
            prog_stack.push(str(1))
            return

        op_false()
        return

    def op_numequal():
        #Returns 1 if the numbers are equal, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a == b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_numequalverify():
        #Same as OP_NUMEQUAL, but runs OP_VERIFY afterward.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a == b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))

        #verify
        if(prog_stack.is_empty()):
            logging.warning("Stack is empty")
            invalidate()
            return

        if(not(int(prog_stack.pop()))):
            logging.warning('Transaction not valid!')
            invalidate()
        return

    def op_numnotequal():
        #Returns 1 if the numbers are not equal, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a != b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_lessthan():
        #Returns 1 if a is less than b, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a < b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_greaterthan():
        #Returns 1 if a is greater than b, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a > b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_lessthanorequal():
        #Returns 1 if a is less than or equal to b, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a <= b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_greaterthanorequal():
        #Returns 1 if a is greater than or equal to b, 0 otherwise.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a >= b):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return

    def op_min():
        #Returns the smaller of a and b.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a < b):
            prog_stack.push(str(a))
            return

        prog_stack.push(str(b))
        return

    def op_max():
        #Returns the larger of a and b.
        if(prog_stack.size() < 2):
            logging.warning("Not enough arguments")
            invalidate()
            return

        a = int(prog_stack.pop())
        b = int(prog_stack.pop())

        if(a > b):
            prog_stack.push(str(a))
            return

        prog_stack.push(str(b))
        return

    def op_within():
        #Returns 1 if x is within the specified range (left-inclusive), 0 otherwise.
        if(prog_stack.size() < 3):
            logging.warning("Not enough arguments")
            invalidate()
            return

        x = int(prog_stack.pop())
        mini = int(prog_stack.pop())
        maxi = int(prog_stack.pop())

        if(mini <= x and x < maxi):
            prog_stack.push(str(1))
            return

        prog_stack.push(str(0))
        return


    

    """
    OPLIST:
    This is the dictionary used by the fetch-and-execute loop to parse
    opcode strings into proper operations. Proper operations will then be
    executed. Any command string that matches one of the opcodes will be
    treated like an operation.
    """
    global operations
    operations = {
        # opcode                     # proper operation
        'OP_RIPEMD160':               op_ripemd160,
        'OP_SHA1':                    op_sha1,
        'OP_SHA256':                  op_sha256,
        'OP_HASH256':                 op_hash256,
        'OP_HASH160':                 op_hash160,
        'OP_VERIFYSIG':               op_checksig,
        'OP_CHECKSIG':                op_checksig,
        'OP_CHECKSIGVERIFY':          op_checksigverify,

        'OP_NOP':                     op_nop,
        'OP_EQUAL':                   op_equal,
        'OP_VERIFY':                  op_verify,
        'OP_IF':                      op_if,
        'OP_NOTIF':                   op_notif,
        'OP_ELSE':                    op_else,
        'OP_ENDIF':                   op_endif,
        'OP_RETURN':                  op_return,

        'OP_DUP':                     op_dup,
        'OP_DROP':                    op_drop,

        'OP_CHECKLOCKTIME':           op_checklocktime,
        'OP_CHECKLOCKTIMEVERIFY':     op_checklocktime,
        'OP_NOP2':                    op_checklocktime,

        'OP_EQUALVERIFY':             op_equalverify,
        'OP_INVERT':                  op_invert,
        'OP_AND':                     op_and,
        'OP_OR':                      op_or,
        'OP_XOR':                     op_xor,
        'OP_TRUE':                    op_true,
        'OP_1':                       op_true,
        'OP_FALSE':                   op_false,
        'OP_0':                       op_false,
        'OP_1NEGATE':                 op_1negate,

        'OP_TOALTSTACK':              op_toaltstack,
        'OP_FROMALTSTACK':            op_fromaltstack,
        'OP_IFDUP':                   op_ifdup,
        'OP_NIP':                     op_nip,
        'OP_OVER':                    op_over,
        'OP_PICK':                    op_pick,
        'OP_ROLL':                    op_roll,
        'OP_ROT':                     op_rot,
        'OP_SWAP':                    op_swap,
        'OP_TUCK':                    op_tuck,
        'OP_2DROP':                   op_2drop,
        'OP_2DUP':                    op_2dup,
        'OP_3DUP':                    op_3dup,
        'OP_2OVER':                   op_2over,
        'OP_2ROT':                    op_2rot,
        'OP_2SWAP':                   op_2swap,

        'OP_1ADD':                    op_1add,
        'OP_1SUB':                    op_1sub,
        'OP_2MUL':                    op_2mul,
        'OP_2DIV':                    op_2div,
        'OP_NOT':                     op_not,
        'OP_0NOTEQUAL':               op_0notequal,
        'OP_ADD':                     op_add,
        'OP_SUB':                     op_sub,
        'OP_MUL':                     op_mul,
        'OP_DIV':                     op_div,
        'OP_MOD':                     op_mod,
        'OP_BOOLAND':                 op_booland,
        'OP_BOOLOR':                  op_boolor,
        'OP_NUMEQUAL':                op_numequal,
        'OP_NUMEQUALVERIFY':          op_numequalverify,
        'OP_NUMNOTEQUAL':             op_numnotequal,
        'OP_LESSTHAN':                op_lessthan,
        'OP_GREATERTHAN':             op_greaterthan,
        'OP_LESSTHANOREQUAL':         op_lessthanorequal,
        'OP_GREATERTHANOREQUAL':      op_greaterthanorequal,
        'OP_MIN':                     op_min,
        'OP_MAX':                     op_max,
        'OP_WITHIN':                  op_within,

        'OP_NOP1':                    op_nop,
        'OP_NOP4':                    op_nop,
        'OP_NOP5':                    op_nop,
        'OP_NOP6':                    op_nop,
        'OP_NOP7':                    op_nop,
        'OP_NOP8':                    op_nop,
        'OP_NOP9':                    op_nop,
        'OP_NOP10':                   op_nop,
        }

    def if_endif_syntax_check(self):
        """
        Checks whether the program contains proper if/endif syntax as
        specified in the documentation. 
        """
        global operations

        counter = 0

        pq_copy = self.prog_queue.copy()
        # go through the program queue and convert all opcodes into
            # proper operations

        ifs = {'OP_IF', 'OP_NOTIF'}
        elses = {'OP_ELSE'}
        endifs = {'OP_ENDIF'}

        # Ifs increase the counter, endifs decrease it. Program is only valid
        # when the counter is 0 at the end and all existing elses occured
        # when the counter was greater than zero.
        for command in pq_copy:
            if command in ifs:
                counter += 1
            if command in endifs:
                counter -= 1
            if command in elses and counter == 0:
                invalidate()

        if counter != 0:
            invalidate()


    def execute_script(self, prog_stacky: LabStack, printstack = 0):
        """
        Calling this instance method upon a LabScript instance executes the
        script. 
        """
        global prog_stack
        prog_stack = prog_stacky
        global validity
        validity = True

        global alt_stack
        alt_stack = LabStack()  # program memory

        global control_flow_stack
        control_flow_stack = LabStack()

        """
            stack used for control flow. The topmost entry informs the program
            whether the oncoming flow of operations can be executed, as allowed
            or disallowed by any recent conditional operations. this acts like
            a state machine. We need these flags to prevent execution of else
            statements across layered if-blocks.
        """

        ALLOW_ALL=0 # Any operation can be executed.
        ALLOW_IF_ELSE=1 # Nothing but ifs, elses and endifs can be executed.
        ALLOW_IF=2  # Nothing but ifs and endifs can be executed. 
        # To understand what all of this crap means, execute this code on
        # paper and write down what flags are pushed when:
        """    
             OP_IF (true)
             OP_NOP
             OP_ELSE
             OP_IF
             OP_NOP
             OP_ELSE
             OP_NOP
             OP_ENDIF
             OP_ELSE
             OP_NOP
             OP_ENDIF
        """
        
        control_flow_stack.push(ALLOW_ALL)

        
        #This loop keeps fetching commands from the prog_queue and tries to
        #interpret and execute them, until end of program is reached.
        while(self.pc <= self.pend):

            #global validity
            self.valid = validity
            # Check for validity. If invalid, stop executing.
            if not self.valid:
                logging.warning("[!] Error: Invalid.")
                return 0

            next_item = self.prog_queue[self.pc-1] # Fetch next item
            operationstring = next_item

            pushed = 0

            # Check if item is data or opcode. If data, push onto stack.
            if (next_item not in operations):
                if control_flow_stack.peek() == ALLOW_ALL:
                    prog_stack.push(next_item)
                    pushed = 1

                #print
                if(printstack):
                    print("--------------------------")
                    print("SCRIPT: \"" + self.to_string() + "\"")
                    print("--------------------------")
                    if(pushed):
                        print("PUSHED:")
                    else:
                        print("DIDN'T PUSH:")
                    print(str(operationstring) + "\n")
                    print("COUNTER:")
                    print("programm_end: " + str(self.pend))
                    print("programm_step: " + str(self.pc))
                    print("\n")
                    print("STACK:")
                    prog_stack.print_stack()
                    print("\nCONTROL_FLOW_STACK:")
                    control_flow_stack.print_stack()
                    print("--------------------------")
                    #input()

                self.pc = self.pc + 1

                continue
            
            op = operations[next_item] # Proper operation to be executed

            # Check if op_code is op_if or op_endif. Always execute
            # these operations.
            if operationstring in {'OP_IF', 'OP_ENDIF'}:
                op() # EXECUTION

            # Check if op_code is op_else. Only allow this operation if
            # the control flow flag is ALLOW_ELSE.
            elif control_flow_stack.peek() == ALLOW_IF_ELSE:
                if operationstring == 'OP_ELSE':
                    op() # EXECUTION

            # If op_code is any other proper operation, execute it only
            # if the current control flow allows it. It won't get performed
            # if we are in an if/else-block that was evaluated to false.
            elif control_flow_stack.peek() == ALLOW_ALL:
                op() # EXECUTION

            #if the printstack argument is given, the stack is printed after each step.

            if(printstack):
                print("--------------------------")
                print("SCRIPT: \"" + self.to_string() + "\"")
                print("--------------------------")
                print("OPERATION:")
                print(str(operationstring) + "\n")
                print("COUNTER:")
                print("programm_end: " + str(self.pend))
                print("programm_step: " + str(self.pc) + "\n")
                print("STACK:")
                prog_stack.print_stack()
                print("\nCONTROL_FLOW_STACK:")
                control_flow_stack.print_stack()
                print("--------------------------")
                #input()

            self.pc= self.pc + 1

        # If Progstack is empty or TRUE is on top return true otherwise
        # invalidate and return FALSE
        if (prog_stack.is_empty() or (prog_stack.size() == 1 and prog_stack.peek() == '1')):
            return 1
        else:
            invalidate()
            logging.warning("[!] Error: Invalid Tx.")
            return 0

        
