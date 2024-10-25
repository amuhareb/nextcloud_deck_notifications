import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_DATABASE'),
}

def initialize_database():
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor()
    # Create assignment_notifications table
    query = f"""
    CREATE TABLE IF NOT EXISTS {os.getenv('ASSIGNMENT_TABLE')} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        card_id INT NOT NULL,
        participant VARCHAR(255) NOT NULL,
        notified BOOLEAN DEFAULT FALSE
    )
    """
    cursor.execute(query)
    cnx.commit()
    cursor.close()
    cnx.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    initialize_database()
