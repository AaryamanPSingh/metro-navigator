import heapq
from collections import defaultdict
from database import get_connection

def build_graph():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    graph = defaultdict(list)
    
    # Add same-line edges from Connection table
    cursor.execute('''
        SELECT c.station1_id, c.station2_id, c.travel_time,
               sl.line_id
        FROM Connection c
        JOIN StationLine sl ON c.station1_id = sl.station_id
        JOIN StationLine sl2 ON c.station2_id = sl2.station_id
        AND sl.line_id = sl2.line_id
    ''')
    
    for row in cursor.fetchall():
        node1 = (row['station1_id'], row['line_id'])
        node2 = (row['station2_id'], row['line_id'])
        graph[node1].append((node2, row['travel_time']))
    
    # Add interchange edges
    cursor.execute('''
        SELECT sl1.station_id, sl1.line_id as line1, sl2.line_id as line2
        FROM StationLine sl1
        JOIN StationLine sl2 ON sl1.station_id = sl2.station_id
        AND sl1.line_id != sl2.line_id
    ''')
    
    for row in cursor.fetchall():
        node1 = (row['station_id'], row['line1'])
        node2 = (row['station_id'], row['line2'])
        graph[node1].append((node2, 5))
    
    conn.close()
    return graph

def dijkstra(graph, start_station_id, end_station_id):
    start_nodes = [node for node in graph if node[0] == start_station_id]
    end_nodes = set(node for node in graph if node[0] == end_station_id)
    
    if not start_nodes or not end_nodes:
        return None, None
    
    pq = [(0, start_nodes[0], [start_nodes[0]])]
    visited = set()
    
    while pq:
        cost, current, path = heapq.heappop(pq)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current in end_nodes:
            return cost, path
        
        for neighbor, weight in graph[current]:
            if neighbor not in visited:
                heapq.heappush(pq, (cost + weight, neighbor, path + [neighbor]))
    
    return None, None

def get_path_details(path):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    result = []
    for station_id, line_id in path:
        cursor.execute('SELECT name FROM Station WHERE station_id = %s', (station_id,))
        station = cursor.fetchone()
        cursor.execute('SELECT name FROM Line WHERE line_id = %s', (line_id,))
        line = cursor.fetchone()
        result.append((station['name'], line['name']))
    
    conn.close()
    return result

if __name__ == "__main__":
    print("Building graph...")
    graph = build_graph()
    print(f"Graph built with {len(graph)} nodes")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT station_id FROM Station WHERE name = 'Dwarka Sector 21'")
    start = cursor.fetchone()

    cursor.execute("SELECT station_id FROM Station WHERE name = 'Hauz Khas'")
    end = cursor.fetchone()
    
    conn.close()
    
    if not start or not end:
        print("Station not found")
    else:
        cost, path = dijkstra(graph, start['station_id'], end['station_id'])
        print(f"Shortest path cost: {cost} minutes")
        print(f"Number of stops: {len(path)}")
        print(f"Path: {path}")
        details = get_path_details(path)
        for station, line in details:
            print(f"{station} ({line})")