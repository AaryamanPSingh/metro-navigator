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

def calculate_fare(num_stops):
    distance = num_stops * 1.5
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT amount FROM Fare 
        WHERE min_distance <= %s AND max_distance > %s
    ''', (distance, distance))
    fare = cursor.fetchone()
    conn.close()
    return fare['amount'] if fare else 60

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
    fare = calculate_fare(len(path))
    
    return render_template('result.html', 
                         details=details,
                         cost=cost,
                         fare=fare,
                         source=source,
                         destination=destination,
                         stops=len(path))

if __name__ == '__main__':
    app.run(debug=True)