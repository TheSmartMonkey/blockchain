from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto import Random

# Set of functions to support all cryptographic operation
def hash_string(paramStr):
    return SHA256.new(paramStr.encode()).hexdigest()

def generate_key_couple():
    random_generator=Random.new().read
    newKey = RSA.generate(2048,random_generator)
    private_key = newKey.exportKey("PEM")
    public_key = newKey.publickey().exportKey("PEM")
    rsa_private_key = RSA.import_key(private_key)
    rsa_public_key = RSA.import_key(public_key)
    return rsa_private_key,rsa_public_key

def sign_message(message,private_key):
    h = SHA256.new(message.encode())
    signature = pkcs1_15.new(RSA.import_key(private_key)).sign(h)
    return signature.hex()

def check_signature(message,signature,public_key):
    try:
        h = SHA256.new(message.encode())
        pkcs1_15.new(RSA.import_key(public_key)).verify(h,bytearray.fromhex(signature))
        return True
    except:
        return False



