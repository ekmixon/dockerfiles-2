from cryptography.fernet import Fernet
# Make sure cryptograph works
key = Fernet.generate_key()
print(f"All is good. cryptography generated a key: {key}")
