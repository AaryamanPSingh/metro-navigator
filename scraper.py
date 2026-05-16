import requests
from bs4 import BeautifulSoup
import mysql.connector
from dotenv import load_dotenv
import os
import re

load_dotenv()

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password=os.getenv('DB_PASSWORD'),
    database='metro_navigator'
)
cursor = conn.cursor()

# Clear existing data
cursor.execute('DELETE FROM Connection')
cursor.execute('DELETE FROM StationLine')
cursor.execute('DELETE FROM Station')
cursor.execute('DELETE FROM Line')
cursor.execute('DELETE FROM Fare')

headers = {'User-Agent': 'Mozilla/5.0'}

lines = [
    ('Yellow Line', 'Yellow', 'https://en.wikipedia.org/wiki/Yellow_Line_(Delhi_Metro)'),
    ('Red Line', 'Red', 'https://en.wikipedia.org/wiki/Red_Line_(Delhi_Metro)'),
    ('Blue Line', 'Blue', 'https://en.wikipedia.org/wiki/Blue_Line_(Delhi_Metro)'),
    ('Green Line', 'Green', 'https://en.wikipedia.org/wiki/Green_Line_(Delhi_Metro)'),
    ('Violet Line', 'Violet', 'https://en.wikipedia.org/wiki/Violet_Line_(Delhi_Metro)'),
    ('Pink Line', 'Pink', 'https://en.wikipedia.org/wiki/Pink_Line_(Delhi_Metro)'),
    ('Magenta Line', 'Magenta', 'https://en.wikipedia.org/wiki/Magenta_Line_(Delhi_Metro)'),
]

station_map = {}

def scrape_stations(soup):
    tables = soup.find_all('table', class_='wikitable')
    all_candidates = []
    seen = set()

    for i, table in enumerate(tables):
        rows = table.find_all('tr')
        candidates = []
        for row in rows:
            all_cells = row.find_all(['td', 'th'])
            if len(all_cells) < 2:
                continue
            
            first = re.sub(r'\[.*?\]', '', all_cells[0].get_text(strip=True)).strip()
            
            if first.isdigit():
                name = re.sub(r'\[.*?\]', '', all_cells[1].get_text(strip=True)).strip()
                if name and name not in seen:
                    candidates.append(name)
                    seen.add(name)
        
        print(f"  Table {i}: {len(candidates)} candidates")
        all_candidates.extend(candidates)

    return all_candidates

for line_name, color, url in lines:
    print(f"Scraping {line_name}...")
    
    cursor.execute('INSERT INTO Line (name, color) VALUES (%s, %s)', (line_name, color))
    line_id = cursor.lastrowid
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    stations = scrape_stations(soup)  # pass soup not url
    
    for i, station_name in enumerate(stations):
        if station_name not in station_map:
            cursor.execute('INSERT INTO Station (name) VALUES (%s)', (station_name,))
            station_map[station_name] = cursor.lastrowid
        
        station_id = station_map[station_name]
        
        try:
            cursor.execute(
                'INSERT IGNORE INTO StationLine (station_id, line_id, sequence_number) VALUES (%s, %s, %s)',
                (station_id, line_id, i+1)
            )
        except:
            pass
        
        if i > 0:
            prev_id = station_map[stations[i-1]]
            cursor.execute(
                'INSERT INTO Connection (station1_id, station2_id, distance, travel_time) VALUES (%s, %s, %s, %s)',
                (station_id, prev_id, 1.5, 3)
            )
            cursor.execute(
                'INSERT INTO Connection (station1_id, station2_id, distance, travel_time) VALUES (%s, %s, %s, %s)',
                (prev_id, station_id, 1.5, 3)
            )

# Fare structure
fares = [
    (0, 2, 10),
    (2, 5, 20),
    (5, 12, 30),
    (12, 21, 40),
    (21, 32, 50),
    (32, 999, 60),
]
cursor.executemany(
    'INSERT INTO Fare (min_distance, max_distance, amount) VALUES (%s, %s, %s)',
    fares
)

conn.commit()
conn.close()
print(f"Done — {len(station_map)} unique stations")