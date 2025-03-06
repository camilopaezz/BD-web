import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    """
    Create and return a connection to the MySQL database using environment variables
    """
    try:
        connection = mysql.connector.connect(
            host=os.environ.get('DB_HOST'),
            port=3306,
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD')
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def execute_query(query, params=None, fetch_mode=None):
    """
    Execute a query and optionally return results
    
    Parameters:
    - query: SQL query to execute
    - params: Parameters for the query (optional)
    - fetch_mode: 'one' to fetch one result, 'all' to fetch all results, None for no results
    
    Returns:
    - Query results or None
    """
    connection = get_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if fetch_mode == 'one':
            result = cursor.fetchone()
        elif fetch_mode == 'all':
            result = cursor.fetchall()
        else:
            connection.commit()
            result = None
            
        return result
    except Error as e:
        print(f"Error executing query: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
