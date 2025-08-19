from werkzeug.security import generate_password_hash

hash_value = generate_password_hash("12345")
print(hash_value)