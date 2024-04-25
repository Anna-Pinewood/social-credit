import sqlite3

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('estimation_bot.db')
cursor = conn.cursor()

# Create a table
cursor.execute('''CREATE TABLE IF NOT EXISTS user_estimations
               (id INTEGER PRIMARY KEY, username TEXT, estimated_user TEXT, estimation TEXT, comment TEXT)''')

# Commit changes and close the connection
conn.commit()
conn.close()
