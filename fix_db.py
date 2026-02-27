from app import app, mysql

with app.app_context():
    cursor = mysql.connection.cursor()
    
    # This is the exact command we were trying to run in Workbench!
    cursor.execute("ALTER TABLE marketplace MODIFY image_file VARCHAR(255);")
    mysql.connection.commit()
    
    cursor.close()
    print("Success! The database column is now fixed.")