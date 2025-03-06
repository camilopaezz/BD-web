import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()

# Obtener datos de conexión desde el entorno
host = os.environ.get('DB_HOST')
user = os.environ.get('DB_USER')
password = os.environ.get('DB_PASSWORD')
database = os.environ.get('DB_NAME')

connection_str = (
    "DRIVER={MySQL ODBC 9.2 ANSI Driver};"
    f"SERVER={host};"
    "PORT=3306;"
    f"DATABASE={database};"
    f"USER={user};"
    f"PASSWORD={password};"
    "OPTION=3;"
)

try:
    connection = pyodbc.connect(connection_str)
    cursor = connection.cursor()
    
    cursor.execute("SELECT DATABASE()")
    db_actual = cursor.fetchone()[0]
    print("Conectado a la base de datos:", db_actual)
    
    cursor.execute("SHOW TABLES")
    print("Tablas en la base de datos:")
    for row in cursor.fetchall():
        print(row[0])
    
    cursor.close()
    connection.close()

except Exception as e:
    print("Error al conectar:", e)
