import random
import string

def generate_password():
    lowercase_letters = string.ascii_lowercase
    uppercase_letters = string.ascii_uppercase
    digits = string.digits
    special_characters = string.punctuation
    all_characters = lowercase_letters + uppercase_letters + digits + special_characters
    password_length = random.randint(8, 16)
    password = [
        random.choice(lowercase_letters),
        random.choice(uppercase_letters),
        random.choice(digits),
    ]
    for _ in range(password_length - 3):
        password.append(random.choice(all_characters))
    random.shuffle(password)
    return ''.join(password)