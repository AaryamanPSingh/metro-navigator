import mysql.connector
import csv
import os
from dotenv import load_dotenv
from math import radians, sin, cos, sqrt, atan2

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
conn.commit()

# Load stops → Station table
stops = {}
with open('stops.txt', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cursor.execute('''
            INSERT INTO Station (station_id, name, latitude, longitude)
            VALUES (%s, %s, %s, %s)
        ''', (int(row['stop_id']), row['stop_name'].strip(), 
              float(row['stop_lat']), float(row['stop_lon'])))
        stops[row['stop_id']] = row['stop_name'].strip()

conn.commit()
print(f"Loaded {len(stops)} stations")

# Line colors from route_short_name
def get_color(short_name):
    code = short_name.split('_')[0].upper()
    second = short_name.split('_')[1].upper() if len(short_name.split('_')) > 1 else ''
    
    mapping = {
        'R': 'Red',
        'Y': 'Yellow',
        'B': 'Blue',
        'G': 'Green',
        'V': 'Violet',
        'P': 'Pink',
        'M': 'Magenta',
        'O': 'Orange',
        'A': 'Aqua',
    }
    
    # Rapid Metro starts with R_SP
    if code == 'R' and second == 'SP':
        return 'Rapid'
    
    return mapping.get(code, 'Unknown')

# Load routes → Line table
routes = {}
color_to_line = {}
with open('routes.txt', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(repr(row['route_short_name']))
        if row['route_short_name'].endswith('_R'):
            continue
        color = get_color(row['route_short_name'])
        if color not in color_to_line:
            cursor.execute(
                'INSERT INTO Line (name, color) VALUES (%s, %s)',
                (color + ' Line', color)
            )
            conn.commit()  # commit after each insert
            cursor.execute('SELECT LAST_INSERT_ID()')
            line_id = cursor.fetchone()[0]
            color_to_line[color] = line_id
        routes[row['route_id']] = {
            'name': color + ' Line',
            'color': color,
            'line_id': color_to_line[color]
        }

conn.commit()
print(f"Loaded {len(routes)} routes")
print(f"color_to_line: {color_to_line}")
print(f"routes sample: {list(routes.items())[:3]}")
# Load trips → get one trip per route
trip_to_route = {}
route_to_trip = {}
with open('trips.txt', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        route_id = row['route_id']
        trip_id = row['trip_id']
        trip_to_route[trip_id] = route_id
        # Only keep trips for routes we loaded (forward routes only)
        if route_id in routes and route_id not in route_to_trip:
            route_to_trip[route_id] = trip_id

print(f"Routes with trips: {len(route_to_trip)}")

# Load stop_times for representative trips
# Group by trip_id, only process our selected trips
selected_trips = set(route_to_trip.values())
trip_stops = {}  # trip_id -> sorted list of (sequence, stop_id, dist, arrival, departure)

with open('stop_times.txt', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['trip_id'] in selected_trips:
            trip_id = row['trip_id']
            if trip_id not in trip_stops:
                trip_stops[trip_id] = []
            trip_stops[trip_id].append({
                'sequence': int(row['stop_sequence']),
                'stop_id': row['stop_id'],
                'dist': float(row['shape_dist_traveled']),
                'arrival': row['arrival_time'],
                'departure': row['departure_time']
            })

# Sort each trip by sequence
for trip_id in trip_stops:
    trip_stops[trip_id].sort(key=lambda x: x['sequence'])

print(f"Loaded stop times for {len(trip_stops)} trips")

# Build StationLine and Connection tables
def time_to_minutes(t):
    parts = t.split(':')
    return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60

for route_id, trip_id in route_to_trip.items():
    if trip_id not in trip_stops:
        continue
    
    stops_list = trip_stops[trip_id]
    line_id = routes[route_id]['line_id']
    
    for i, stop in enumerate(stops_list):
        station_id = int(stop['stop_id'])
        
        # Insert StationLine
        try:
            cursor.execute('''
                INSERT IGNORE INTO StationLine (station_id, line_id, sequence_number)
                VALUES (%s, %s, %s)
            ''', (station_id, line_id, stop['sequence']))
        except:
            pass
        
        # Insert Connection to previous stop
        if i > 0:
            prev = stops_list[i-1]
            prev_station_id = int(prev['stop_id'])
            
            # Real distance in meters → km
            dist_km = round((stop['dist'] - prev['dist']) / 1000, 3)
            
            # Real travel time in minutes
            travel_time = round(time_to_minutes(stop['arrival']) - 
                              time_to_minutes(prev['departure']), 1)
            
            # Handle negative times (overnight)
            if travel_time < 0:
                travel_time = abs(travel_time)
            
            try:
                cursor.execute('''
                    INSERT INTO Connection (station1_id, station2_id, distance, travel_time)
                    VALUES (%s, %s, %s, %s)
                ''', (station_id, prev_station_id, dist_km, travel_time))
                cursor.execute('''
                    INSERT INTO Connection (station1_id, station2_id, distance, travel_time)
                    VALUES (%s, %s, %s, %s)
                ''', (prev_station_id, station_id, dist_km, travel_time))
            except:
                pass

conn.commit()

# Add fare structure
fares = [
    (0, 2, 11),
    (2, 5, 21),
    (5, 12, 32),
    (12, 21, 43),
    (21, 32, 54),
    (32, 999, 64),
]
cursor.executemany(
    'INSERT INTO Fare (min_distance, max_distance, amount) VALUES (%s, %s, %s)',
    fares
)
conn.commit()
conn.close()
print("Done — database built from official GTFS data")