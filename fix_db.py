import sqlite3

def fix_database():
    db = sqlite3.connect('database.sqlite')
    cursor = db.cursor()
    
    # Get existing columns
    try:
        cursor.execute("PRAGMA table_info(Guilds)")
        existing_columns = [row[1] for row in cursor.fetchall()]
    except:
        existing_columns = []

    # If table doesn't exist at all, create it
    if not existing_columns:
        print("Creating Guilds table from scratch...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Guilds (
                guildId TEXT PRIMARY KEY, 
                welcomeChannelId TEXT, 
                logChannelId TEXT, 
                verificationRoleId TEXT, 
                autoModEnabled INTEGER DEFAULT 1, 
                bannedWords TEXT DEFAULT '[]', 
                ticketCategoryId TEXT, 
                ticketLogChannelId TEXT, 
                suggestionChannelId TEXT, 
                autoRoleId TEXT, 
                themeColor TEXT DEFAULT '#3498DB'
            )
        """)
    else:
        # Check and add each potential missing column
        all_columns = {
            "welcomeChannelId": "TEXT",
            "logChannelId": "TEXT",
            "reportChannelId": "TEXT",
            "verificationRoleId": "TEXT",
            "autoModEnabled": "INTEGER DEFAULT 1",
            "bannedWords": "TEXT DEFAULT '[]'",
            "ticketCategoryId": "TEXT",
            "ticketLogChannelId": "TEXT",
            "suggestionChannelId": "TEXT",
            "autoRoleId": "TEXT",
            "staffRoleId": "TEXT",
            "themeColor": "TEXT DEFAULT '#3498DB'",
            "appReviewChannelId": "TEXT",
            "appQuestions": "TEXT DEFAULT '[\"What is your name?\", \"How old are you?\", \"Why do you want to join?\"]'"
        }
        
        for col, col_type in all_columns.items():
            if col not in existing_columns:
                print(f"Adding missing column: {col}")
                try:
                    cursor.execute(f"ALTER TABLE Guilds ADD COLUMN {col} {col_type}")
                except Exception as e:
                    print(f"Error adding {col}: {e}")

    db.commit()
    db.close()
    print("✅ Database repair complete!")

if __name__ == "__main__":
    fix_database()
