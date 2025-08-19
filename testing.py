import oracledb
import os

# Path to wallet directory
WALLET_PATH = r"C:/codes/monitering/new_monitering/backend/Wallet_CLOUDAREPRJ"  # Update this to your wallet folder

# Database username and password
DB_USER = "cloudeye"  # Replace with your username
DB_PASSWORD = "Cloudare@12345678"  # Replace with your password

# TNS alias from tnsnames.ora inside the wallet folder (e.g., dbname_tp)
DB_TNS = "cloudareprj_tp"  

# Initialize connection using wallet
connection = oracledb.connect(
    user=DB_USER,
    password=DB_PASSWORD,
    dsn=DB_TNS,
    config_dir=WALLET_PATH,        # Wallet directory containing sqlnet.ora & tnsnames.ora
    wallet_location=WALLET_PATH,    # Wallet directory
    wallet_password="Cloudare@123456"
)

print("Connected to ATP Database")
cursor = connection.cursor()
cursor.execute("SELECT sysdate FROM dual")
for row in cursor:
    print("DB Date:", row[0])

cursor.close()
connection.close()
