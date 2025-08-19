import oracledb
import os
import serverdata as sd

# Initialize connection using wallet
def get_db():
    connection = oracledb.connect(
        user=sd.DB_USER,
        password=sd.DB_PASSWORD,
        dsn=sd.DB_TNS,
        config_dir=sd.WALLET_PATH,        # Wallet directory containing sqlnet.ora & tnsnames.ora
        wallet_location=sd.WALLET_PATH,    # Wallet directory
        wallet_password=sd.WALLET_PASSWORD
    )

    print("Connected to ATP Database")
    return connection
    # cursor = connection.cursor()
    # return cursor
    # cursor.execute("SELECT sysdate FROM dual")
    # for row in cursor:
    #     print("DB Date:", row[0])

    # cursor.close()
    # connection.close()
