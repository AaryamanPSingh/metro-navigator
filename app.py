from flask import Flask, render_template, request
from database import get_connection
from djikstra import build_graph, dijkstra, get_path_details

app = Flask(__name__)

print("Building graph...")
graph = build_graph()
print("Graph ready")

def get_all_stations():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT station_id, name FROM Station ORDER BY name')
    stations = cursor.fetchall()
    conn.close()
    return stations

def calculate_fare(path):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get Orange Line id
    cursor.execute("SELECT line_id FROM Line WHERE color = 'Orange'")
    orange = cursor.fetchone()
    orange_line_id = orange['line_id'] if orange else None
    cursor.fetchall()
    
    regular_distance = 0
    airport_express_distance = 0
    airport_express_start = None
    airport_express_end = None
    
    for i in range(1, len(path)):
        station1_id = path[i-1][0]
        station2_id = path[i][0]
        line_id = path[i][1]
        
        if station1_id == station2_id:
            continue
        
        cursor.execute('''
            SELECT distance FROM Connection 
            WHERE station1_id = %s AND station2_id = %s
        ''', (station1_id, station2_id))
        result = cursor.fetchone()
        cursor.fetchall()
        dist = result['distance'] if result else 0
        
        if line_id == orange_line_id:
            if airport_express_start is None:
                airport_express_start = station1_id
            airport_express_end = station2_id
            airport_express_distance += dist
        else:
            regular_distance += dist
    
    # Airport Express fare lookup
    airport_express_fare = 0
    if airport_express_start and airport_express_end:
        cursor.execute('SELECT name FROM Station WHERE station_id = %s', (airport_express_start,))
        from_name = cursor.fetchone()['name']
        cursor.fetchall()
        cursor.execute('SELECT name FROM Station WHERE station_id = %s', (airport_express_end,))
        to_name = cursor.fetchone()['name']
        cursor.fetchall()
        
        cursor.execute('''
            SELECT amount FROM AirportExpressFare 
            WHERE from_station = %s AND to_station = %s
        ''', (from_name, to_name))
        ae_fare = cursor.fetchone()
        cursor.fetchall()
        airport_express_fare = ae_fare['amount'] if ae_fare else 64
    
    # Regular DMRC fare based on regular distance only
    regular_fare = 0
    if regular_distance > 0:
        cursor.execute('''
            SELECT amount FROM Fare 
            WHERE min_distance <= %s AND max_distance > %s
        ''', (regular_distance, regular_distance))
        fare = cursor.fetchone()
        cursor.fetchall()
        regular_fare = fare['amount'] if fare else 64
    
    conn.close()
    
    total_distance = round(regular_distance + airport_express_distance, 2)
    total_fare = regular_fare + airport_express_fare
    
    return total_fare, total_distance

@app.route('/')
def index():
    stations = get_all_stations()
    return render_template('index.html', stations=stations)

@app.route('/search', methods=['POST'])
def search():
    source = request.form['source']
    destination = request.form['destination']
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT station_id FROM Station WHERE name = %s', (source,))
    start = cursor.fetchone()
    cursor.execute('SELECT station_id FROM Station WHERE name = %s', (destination,))
    end = cursor.fetchone()
    conn.close()
    
    if not start or not end:
        return render_template('index.html', error="Station not found", stations=get_all_stations())
    
    cost, path = dijkstra(graph, start['station_id'], end['station_id'])
    
    if not path:
        return render_template('index.html', error="No path found", stations=get_all_stations())
    
    details = get_path_details(path)
    fare, distance = calculate_fare(path)

    return render_template('result.html', 
                     details=details,
                     cost=cost,
                     fare=fare,
                     distance=distance,
                     source=source,
                     destination=destination,
                     stops=len(details))

if __name__ == '__main__':
    app.run(debug=True)