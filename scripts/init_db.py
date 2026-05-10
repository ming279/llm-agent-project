import sys
import os
import mysql.connector

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.config.settings import DB_CONFIG


def init_database():
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        print(f"Database '{DB_CONFIG['database']}' created or already exists")

        cursor.execute(f"USE {DB_CONFIG['database']}")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS websites (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url VARCHAR(500) NOT NULL UNIQUE,
                last_checked TIMESTAMP NULL,
                last_changed TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Websites table created or already exists")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS website_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                website_id INT NOT NULL,
                title VARCHAR(500),
                content TEXT,
                keywords TEXT,
                change_type VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
            )
        ''')
        print("Website_data table created or already exists")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS website_changes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                website_id INT NOT NULL,
                old_title VARCHAR(500),
                new_title VARCHAR(500),
                old_content TEXT,
                new_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
            )
        ''')
        print("Website_changes table created or already exists")

        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialization completed successfully")

    except Exception as e:
        print(f"Error initializing database: {e}")


if __name__ == "__main__":
    init_database()