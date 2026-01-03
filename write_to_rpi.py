import psycopg2
import time


with open("password.txt", "r") as f:
    pwd = f.readline()

pwd = pwd.strip()

conn = psycopg2.connect(
    host="192.168.1.177",
    database="sensor_data",
    user="admin",
    password=pwd
)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS readings (
        id SERIAL PRIMARY KEY,
        timestamp REAL,
        sensor_id TEXT,
        value REAL
    )
''')

cursor.execute('INSERT INTO readings (timestamp, sensor_id, value) VALUES (%s, %s, %s)',
               (time.time(), 'rs485_sensor', 23.5))
conn.commit()
conn.close()
