import sqlite3
import os
import sys

def repair():
    print("--- Database Repair Tool ---")
    db_path = os.path.join(os.getcwd(), "database.sqlite")
    print(f"Opening database: {db_path}")
    
    if not os.path.exists(db_path):
        print("Error: database.sqlite not found!")
        return

    try:
        db = sqlite3.connect(db_path)
        cursor = db.cursor()
        
        # Check Guilds table
        cursor.execute("PRAGMA table_info(Guilds)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current columns in Guilds: {columns}")
        
        needed_guilds = [
            ("staffRoleId", "TEXT"),
            ("reportChannelId", "TEXT"),
            ("appReviewChannelId", "TEXT"),
            ("ticketCategoryId", "TEXT"),
            ("ticketLogChannelId", "TEXT")
        ]
        
        for col, col_type in needed_guilds:
            if col not in columns:
                print(f"Adding missing column: {col}...")
                try:
                    cursor.execute(f"ALTER TABLE Guilds ADD COLUMN {col} {col_type}")
                    print(f"Successfully added {col}")
                except Exception as e:
                    print(f"Error adding {col}: {e}")
            else:
                print(f"Column {col} already exists.")

        # Check Users table
        cursor.execute("PRAGMA table_info(Users)")
        columns_users = [row[1] for row in cursor.fetchall()]
        needed_users = [("username", "TEXT"), ("avatar", "TEXT")]
        for col, col_type in needed_users:
            if col not in columns_users:
                print(f"Adding missing column to Users: {col}...")
                try:
                    cursor.execute(f"ALTER TABLE Users ADD COLUMN {col} {col_type}")
                except Exception as e:
                    print(f"Error adding {col}: {e}")

        db.commit()
        db.close()
        print("--- Repair Complete ---")
    except Exception as e:
        print(f"Fatal Repair Error: {e}")

if __name__ == "__main__":
    repair()
