import json
from time import time

from bccrypto import hash_string,sign_message,check_signature,generate_key_couple

import logging
logger = logging.getLogger(__name__)


class JsonObject(object):
    """
        Object that can be intialized and rendered as a json string
    """
    def __init__(self,jsonString):
        self.__dict__.update(json.loads(jsonString))
    
    def __repr__(self):
        return f"{self.__class__} {self.to_json()}"

    def to_dict(self):
        return(vars(self).copy())

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True)

class Transaction(JsonObject):
    def __init__(self,sender,recipient,amount):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount

    def sign(self,private_key):
        return sign_message(self.to_json(),private_key)

    def is_valid(self,public_key):
        return self.amount > 0 and self.sender == hash_string(public_key)

class SignedTransaction(JsonObject):
    def __init__(self,transaction,signature,public_key):
        self.transaction = transaction
        self.signature = signature
        self.public_key = public_key

    def is_valid(self):
        return check_signature(self.transaction.to_json(),self.signature,self.public_key) and self.transaction.is_valid(self.public_key)

    def to_dict(self):
        dvars=vars(self).copy()
        dvars["transaction"] = self.transaction.to_dict()
        dvars["public_key"] = self.public_key
        return dvars

def transaction_from_dict(transaction_dict):
    return Transaction(transaction_dict['sender'],transaction_dict['recipient'],transaction_dict['amount'])

class Block(JsonObject):
    def __init__(self,index,timestamp,proof,previous_hash,transactions):
        self.index = index
        self.timestamp = timestamp
        self.proof = proof
        self.previous_hash = previous_hash
        self.transactions = transactions

    def hash(self):
        return hash_string(self.to_json())
    
    def to_dict(self):
        dvars = vars(self).copy()
        dvars["transactions"] = [t.to_dict() for t in self.transactions]
        return dvars

def block_from_dict(block_dict):
    transactions = [transaction_from_dict(td) for td in block_dict['transactions']]
    return Block(block_dict['index'],block_dict['timestamp'],block_dict['proof'],block_dict['previous_hash'],transactions)

class Blockchain(object):
    def __init__(self):
        self.current_transactions = []
        self.chain = []

        # Create the genesis block
        self.new_block(previous_hash = '1', proof = 100)

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid

        :param chain: A blockchain
        :return: True if valid, False if not
        """

        previous_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # Check that the hash of the block is correct
            if self.valid_block(previous_block,block):
                previous_block = block
                current_index += 1
            else:
                logger.error("Block not valid:"+block.to_json())
                return False
        return True

    def iter_transaction(self):
        for block in self.chain:
            for transaction in block.transactions:
                yield transaction,"validated"

        for transaction in self.current_transactions:
            yield transaction,"pending"

    def valid_block(self,previous_block,block):
        # Check that the hash of the block is correct and that the proof is valid
        logger.debug("previous_hash:"+previous_block.hash())
        logger.debug("block previous_hash:"+block.previous_hash)
        logger.debug("previous_block.proof: %d"%previous_block.proof)
        logger.debug("block.proof:%d"%block.proof)
        if block.previous_hash != previous_block.hash():
            logger.debug("bad previous hash")
            return False
        if not self.valid_proof(previous_block.proof, block.proof, previous_block.hash()):
            logger.debug("bad proof")
            return False

        return True

    def new_block(self, proof, previous_hash):
        """
        Create a new Block in the Blockchain

        :param proof: The proof given by the Proof of Work algorithm
        :param previous_hash: Hash of previous Block
        :return: New Block
        """

        block = Block(len(self.chain) + 1,time(),proof,previous_hash,self.current_transactions)

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        logger.info("Received block added")
        return block

    def add_block(self, block):
        """
        Add a new Block in the Blockchain mine by another node

        :param proof: The proof given by the Proof of Work algorithm
        :param previous_hash: Hash of previous Block
        :param transactions list of transactions
        :return: New Block
        """

        if self.valid_block(self.last_block,block):
            # Reset the current list of transactions
            self.current_transactions = []

            self.chain.append(block)
            logger.info("Received block added")
            return True
        else:
            logger.info("Received block rejected")
            return False


    def new_transaction(self, transaction):
        """
        Creates a new transaction to go into the next mined Block
        :param amount: Transaction object
        :return: The index of the Block that will hold this transaction
        """
        self.current_transactions.append(transaction)

        return self.last_block.index + 1

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self):
        """
        Simple Proof of Work Algorithm:

            - Find a number p' such that hash(pp') contains leading 4 zeroes
            - Where p is the previous proof, and p' is the new proof
        
        :return: <int>
        """

        last_proof = self.last_block.proof
        last_hash = self.last_block.hash()

        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        Validates the Proof

        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :param last_hash: <str> The hash of the Previous Block
        :return: <bool> True if correct, False if not.

        """

        guess = f'{last_proof}{proof}{last_hash}'
        guess_hash = hash_string(guess)
        return guess_hash[:4] == "0000"


