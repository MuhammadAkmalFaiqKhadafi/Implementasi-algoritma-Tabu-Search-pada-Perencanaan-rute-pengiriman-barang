import json
import random
from math import radians, cos, sin, sqrt, atan2

# Parameter 
vehicle_capacity = 72
speed = 40  # km/jam
fuel_price = 10000
fuel_consumption = 13  # km/l
cost_per_km = 769
overnight_stay_cost = 100000
rest_cost = 10000
max_daily_hours = 8
max_work_hours = 5
rest_time = 0.5
nginap_time = 8  # jam
service_time_per_demand = 2 / 60 # 2 menit per demand, dikonversi ke jam

def haversine(coord1, coord2):
    if isinstance(coord1[0], str) and isinstance(coord1[1], (tuple, list)):
        coord1 = coord1[1]
    if isinstance(coord2[0], str) and isinstance(coord2[1], (tuple, list)):
        coord2 = coord2[1]
    coord1 = (float(coord1[0]), float(coord1[1]))
    coord2 = (float(coord2[0]), float(coord2[1]))
    R = 6371.0
    lat1, lon1 = radians(float(coord1[0])), radians(float(coord1[1]))
    lat2, lon2 = radians(float(coord2[0])), radians(float(coord2[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def load_input_data():
    with open("data_lokasi.json", "r") as f:
        lokasi = json.load(f)
    depots = {}
    customers = {}
    rest_areas = {}
    menginap_locs = {}

    for item in lokasi:
        if item["type"] == "depot":
            kapasitas = item.get("supply", 72)
            depots[item["name"]] = (item["lat"], item["lon"], kapasitas)
        elif item["type"] == "customer":
            customers[item["name"]] = (item["lat"], item["lon"], item["demand"], item["fee"])
        elif item["type"] == "rest_area":
            rest_areas[item["name"]] = (item["lat"], item["lon"])
        elif item["type"] == "menginap":
           menginap_locs[item["name"]] = (item["lat"], item["lon"])

    return depots, customers, rest_areas, menginap_locs


def generate_virtual_rest_area(last_coord, i=1):
    if isinstance(last_coord[0], str) and isinstance(last_coord[1], (tuple, list)):
        last_coord = last_coord[1]
    lat = float(last_coord[0])
    lon = float(last_coord[1])
    return (lat + 0.01 * i, lon + 0.01 * i)

def generate_virtual_menginap_area(last_coord, i=1):
    if isinstance(last_coord[0], str) and isinstance(last_coord[1], (tuple, list)):
        last_coord = last_coord[1]
    lat = float(last_coord[0])
    lon = float(last_coord[1])
    return (lat + 0.015 * i, lon + 0.015 * i)

def load_vehicle_count():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            return config.get("vehicle_count", 1)
    except:
        return 1

def find_nearest_depot(customer_loc, depots):
    return min(depots.items(), key=lambda d: haversine(customer_loc, d[1][:2]))

def allocate_customers(customers, depots, vehicle_count):
    unassigned = set(customers.keys())
    assignments = []
    depot_list = list(depots.items())

    for i in range(vehicle_count):
        vehicle = {
            "route": [],
            "customers": [],
            "remaining_capacity": vehicle_capacity,
            "depot": None
        }

        # Ambil depot paling dekat dengan pelanggan yang tersisa
        if unassigned:
            first_cust = min(unassigned, key=lambda c: min(
                haversine(customers[c][:2], depot[1][:2]) for depot in depot_list))
            nearest_depot_name, nearest_depot_data = find_nearest_depot(customers[first_cust][:2], depots)
        else:
            nearest_depot_name, nearest_depot_data = depot_list[0]

        vehicle["depot"] = (nearest_depot_name, nearest_depot_data)
        current_loc = nearest_depot_data[:2]

        while unassigned:
            possible = None
            for cust in unassigned:
                demand = customers[cust][2]
                if demand <= vehicle["remaining_capacity"]:
                    dist = haversine(current_loc, customers[cust][:2])
                    if not possible or dist < haversine(current_loc, customers[possible][:2]):
                        possible = cust
            if not possible:
                break
            vehicle["customers"].append(possible)
            vehicle["remaining_capacity"] -= customers[possible][2]
            current_loc = customers[possible][:2]
            unassigned.remove(possible)

        assignments.append(vehicle)
    return assignments

def get_nearest_or_virtual_rest_area(current, rest_areas, counter):
    nearest = None
    min_dist = float('inf')
    for coord in rest_areas.values():
        d = haversine(current, coord)
        if d < min_dist and d <= 10:
            nearest = coord
            min_dist = d
    return nearest if nearest else generate_virtual_rest_area(current, counter)

def get_nearest_or_virtual_menginap(current, menginap_locs, counter):
    nearest = None
    min_dist = float('inf')
    for coord in menginap_locs.values():
        d = haversine(current, coord)
        if d < min_dist and d <= 10:
            nearest = coord
            min_dist = d
    return nearest if nearest else generate_virtual_menginap_area(current, counter)

def calculate_route_metrics(route, customers, depot, rest_areas=None, menginap_locs=None, remaining_capacity=vehicle_capacity):
    total_time = 0
    time_since_rest = 0
    time_since_menginap = 0
    total_distance = 0
    total_revenue = 0
    total_cost = 0
    rest_counter = 0
    nginap_counter = 0
    overnight_stays = 0
    total_travel_time = 0
    total_service_time = 0
    total_rest_time = 0
    total_nginap_time = 0
    vehicle_route = [depot[:2]]
    assigned = []

    for cust in route:
        demand = customers[cust][2]
        if demand > remaining_capacity:
            break  # Stop jika kapasitas tidak cukup lagi
        remaining_capacity -= demand
        cust_coord = customers[cust][:2]
        last_point = vehicle_route[-1]
        last_coord = last_point[1] if isinstance(last_point, tuple) and isinstance(last_point[0], str) else last_point

        # Hitung waktu perjalanan ke titik pelanggan
        dist = haversine(last_coord, cust_coord)
        travel_time = dist / speed

        # Tambahkan ke waktu total dan perjalanan
        total_travel_time += travel_time
        time_since_rest += travel_time
        time_since_menginap += travel_time

        # Cek apakah perlu istirahat
        if time_since_rest >= max_work_hours:
            rest_coord = get_nearest_or_virtual_rest_area(last_coord, rest_areas, rest_counter)
            vehicle_route.append(("rest", rest_coord))
            total_rest_time += rest_time
            total_time += rest_time
            time_since_rest = 0
            total_cost += rest_cost
            rest_counter += 1

        # Cek apakah perlu menginap
        if time_since_menginap > max_daily_hours:
            nginap_coord = get_nearest_or_virtual_menginap(last_coord, menginap_locs, nginap_counter)
            vehicle_route.append(("nginap", nginap_coord))
            total_nginap_time += nginap_time
            time_since_rest = 0
            time_since_menginap = 0
            total_cost += overnight_stay_cost
            nginap_counter += 1
            overnight_stays += 1


        # Tambahkan ke rute dan hitung waktu pelayanan
        vehicle_route.append(cust_coord)
        service_time = customers[cust][2] * service_time_per_demand
        total_service_time += service_time
        total_time += service_time
        time_since_rest += service_time
        time_since_menginap += service_time
        total_distance += dist
        total_revenue += customers[cust][3] * customers[cust][2]
        assigned.append((cust_coord, cust, service_time))
    
    total_work_time = total_travel_time + total_service_time
    total_cost += (total_distance / fuel_consumption) * fuel_price
    total_cost += total_distance * cost_per_km
    profit = total_revenue - total_cost

    return (vehicle_route, assigned, overnight_stays, round(total_distance, 2),
    round(total_revenue, 2),
    round(total_cost, 2),
    round(profit, 2),
    round(total_service_time, 2),
    round(total_rest_time, 2),
    round(total_nginap_time, 2),
    round(total_time, 2),
    round(total_travel_time, 2),
    round(total_work_time, 2)
    )

def tabu_search_vrp(depot, customer_names, customers, rest_areas=None, menginap_locs=None, iterations=500, tabu_tenure=10):
    current_solution = customer_names[:]
    best_solution = current_solution[:]
    best_cost = calculate_route_metrics(best_solution, customers, depot, rest_areas, menginap_locs)[5]  # total cost
    tabu_list = []
    
    for _ in range(iterations):
        neighborhood = []
        for i in range(len(current_solution)):
            for j in range(i + 1, len(current_solution)):
                neighbor = current_solution[:]
                neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
                if (i, j) not in tabu_list:
                    neighborhood.append((neighbor, (i, j)))
        if not neighborhood:
            break
        neighborhood.sort(key=lambda x: calculate_route_metrics(x[0], customers, depot, rest_areas, menginap_locs)[5])
        best_neighbor, move = neighborhood[0]
        current_solution = best_neighbor
        tabu_list.append(move)
        if len(tabu_list) > tabu_tenure:
            tabu_list.pop(0)
        cost = calculate_route_metrics(best_solution, customers, depot, rest_areas, menginap_locs)[5]
        if cost < best_cost:
            best_solution = current_solution[:]
            best_cost = cost
    return calculate_route_metrics(best_solution, customers, depot, rest_areas, menginap_locs)

def run_cmvrp(return_assignments=False):
    depots, customers, rest_areas, menginap_locs = load_input_data()
    data_lokasi = json.load(open("data_lokasi.json"))
    rest_areas = {item["name"]: (item["lat"], item["lon"]) for item in data_lokasi if item["type"] == "rest_area"}
    menginap_locs = {item["name"]: (item["lat"], item["lon"]) for item in data_lokasi if item["type"] == "menginap"}
    vehicle_count = load_vehicle_count()
    assignments = allocate_customers(customers, depots, vehicle_count)
    all_routes = []
    for vehicle in assignments:
        depot_name, depot_data = vehicle["depot"]
        route_data = tabu_search_vrp(depot_data, vehicle["customers"], customers, rest_areas=rest_areas, menginap_locs=menginap_locs)
        all_routes.append(route_data)
    generate_leaflet_html(all_routes, rest_areas, menginap_locs)
    if return_assignments:
        for idx, route in enumerate(all_routes):
            assigned_customers = route[1]
            print(f"\nRute Kendaraan {idx+1}:")
            for coord, cust, service_time in assigned_customers:
                print(f"  - {cust}: koordinat={coord}, waktu pelayanan={service_time:.2f} jam")
        return assignments
    return "vrp_tabu_search_visualisasi.html"

def generate_leaflet_html(routes, rest_areas=None, menginap_locs=None):
    scripts = []
    if rest_areas is None:
        rest_areas = {}
    if menginap_locs is None:
        menginap_locs = {}

    # Baca template HTML
    with open("visual_template.html", "r") as f:
        template = f.read()

    colors = ["red", "blue", "green", "orange", "purple", "brown", "magenta", "cyan", "black"]

    # Iterasi semua rute kendaraan
    for idx, route_tuple in enumerate(routes):
        color = colors[idx % len(colors)]
        route_coords = route_tuple[0]
        route_waypoints = []
        if not route_coords:
            continue

        for pt in route_coords:
            if (
                isinstance(pt, tuple) and
                len(pt) == 2 and
                isinstance(pt[0], str) and
                isinstance(pt[1], tuple) and
                len(pt[1]) == 2 and
                all(isinstance(c, (int, float)) for c in pt[1])
            ):
                label, coord = pt
                lat, lon = float(coord[0]), float(coord[1])

                if label == "rest":
                    popup_text = "Rest Area Manual" if (lat, lon) in rest_areas.values() else "Virtual Rest Area"
                    scripts.append(
                        f"""L.marker([{lat}, {lon}], {{
                            icon: L.icon({{
                                iconUrl: '/static/rest_area.png',
                                iconSize: [25, 41],
                                iconAnchor: [12, 41]
                            }})
                        }}).addTo(map).bindPopup('{popup_text}');"""
                    )
                elif label == "nginap":
                    popup_text = "Lokasi Menginap Manual" if (lat, lon) in menginap_locs.values() else "Virtual Tempat Menginap"
                    scripts.append(
                        f"""L.marker([{lat}, {lon}], {{
                            icon: L.icon({{
                                iconUrl: '/static/menginap.png',
                                iconSize: [25, 41],
                                iconAnchor: [12, 41]
                            }})
                        }}).addTo(map).bindPopup('{popup_text}');"""
                    )
            else:
                route_waypoints.append(pt)

        # Buat waypoint untuk L.Routing
        waypoints = ',\n'.join([
            f"L.latLng({float(pt[0])}, {float(pt[1])})"
            for pt in route_waypoints
            if isinstance(pt, (tuple, list)) and len(pt) == 2 and all(isinstance(x, (int, float)) for x in pt)
        ])
        script = f"""
        L.Routing.control({{
            waypoints: [
                {waypoints}
            ],
            lineOptions: {{
                styles: [{{ color: '{color}', weight: 5 }}]
            }},
            routeWhileDragging: false,
            createMarker: function(i, wp) {{
                return L.marker(wp.latLng);
            }}
        }}).addTo(map);
        """
        scripts.append(script)

    # Ganti placeholder dengan script rute dan marker
    final_html = template.replace("[[ROUTES_HERE]]", "\n".join(scripts))

    # Simpan file hasil visualisasi
    with open("vrp_tabu_search_visualisasi.html", "w") as f:
        f.write(final_html)

        

