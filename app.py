from flask import Flask, render_template, request, redirect, send_file
from cmvrp_tabu_search import (
    run_cmvrp, load_input_data, load_vehicle_count,
    allocate_customers, tabu_search_vrp, fuel_price, fuel_consumption)
import json, os
import pandas as pd

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_kendaraan', methods=['POST'])
def set_kendaraan():
    vehicle_count = request.form.get('vehicle_count', type=int)
    if vehicle_count:
        config = {"vehicle_count": vehicle_count}
        with open("config.json", "w") as f:
            json.dump(config, f)
    return redirect('/')

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    tipe = request.form['type']
    lat = float(request.form['lat'])
    lon = float(request.form['lon'])
    demand = request.form.get('demand', type=int)
    fee = request.form.get('fee', type=int)
    supply = request.form.get('supply', type=int)

    data = {
        "name": name,
        "type": tipe,
        "lat": lat,
        "lon": lon,
        "demand": demand,
        "fee": fee
    }

    if tipe == "depot":
        data["supply"] = supply
    
    if not os.path.exists("data_lokasi.json"):
        with open("data_lokasi.json", "w") as f:
            json.dump([], f)

    with open("data_lokasi.json", "r+") as f:
        lokasi = json.load(f)
        lokasi.append(data)
        f.seek(0)
        json.dump(lokasi, f, indent=4)

    return redirect('/lokasi')

@app.route('/hapus/<int:index>', methods=['POST'])
def hapus(index):
    if os.path.exists("data_lokasi.json"):
        with open("data_lokasi.json", "r+") as f:
            data = json.load(f)
            if 0 <= index < len(data):
                data.pop(index)
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=4)
    return redirect('/lokasi')

@app.route('/lokasi')
def lokasi():
    if os.path.exists("data_lokasi.json"):
        with open("data_lokasi.json", "r") as f:
            data = json.load(f)
    else:
        data = []
    return render_template('lokasi.html', data=data)

@app.route('/visualisasi')
def visualisasi():
    file_path = run_cmvrp()
    return send_file(file_path)

from cmvrp_tabu_search import run_cmvrp, load_input_data

@app.route('/laporan')
def tampilkan_laporan():
    depots, customers, rest_areas, menginap_locs = load_input_data()
    vehicle_count = load_vehicle_count()
    assignments = allocate_customers(customers, depots, vehicle_count)

    total_fuel = total_operasional = total_revenue = 0
    kendaraan_data = []
    laporan_csv = []

    for i, vehicle in enumerate(assignments, start=1):
        customers_list = vehicle.get("customers", [])
        depot_info = vehicle.get("depot", ("Unknown", [0.0, 0.0]))

        if not customers_list:
            row = {
                "kendaraan": f"Kendaraan {i}",
                "jarak": 0,
                "overnight": 0,
                "revenue": 0,
                "biaya": 0,
                "profit": 0
            }
            kendaraan_data.append(row)
            laporan_csv.append({
                "Kendaraan": row["kendaraan"],
                "Jarak Tempuh (km)": 0,
                "Overnight (x)": 0,
                "Waktu Pelayanan (jam)": 0,
                "Waktu Istirahat (jam)": 0,
                "Waktu Menginap (jam)": 0,
                "Waktu Perjalanan (jam)": 0,
                "Total Waktu (jam)": 0,
                "Biaya": 0,
                "Revenue": 0,
                "Profit": 0
            })
            continue

        depot_coord = depot_info[1]
        route_result = tabu_search_vrp(
            depot_coord, customers_list, customers,
            rest_areas=rest_areas, menginap_locs=menginap_locs
        )

        _, _, overnight, dist, revenue, cost, profit, service_time, rest_time, nginap_time, total_time, travel_time, work_time = route_result

        fuel_cost = (dist / fuel_consumption) * fuel_price
        ops_cost = cost - fuel_cost
        total_fuel += fuel_cost
        total_operasional += ops_cost
        total_revenue += revenue

        kendaraan_data.append({
            "kendaraan": f"Kendaraan {i}",
            "jarak": round(dist, 2),
            "overnight": overnight,
            "revenue": round(revenue),
            "biaya": round(cost),
            "profit": round(profit)
        })

        laporan_csv.append({
            "Kendaraan": f"Kendaraan {i}",
            "Jarak Tempuh (km)": round(dist, 2),
            "Overnight (x)": overnight,
            "Waktu Pelayanan (jam)": round(service_time, 2),
            "Waktu Istirahat (jam)": round(rest_time, 2),
            "Waktu Menginap (jam)": round(nginap_time, 2),
            "Waktu Perjalanan (jam)": round(travel_time, 2),
            "Total Waktu (jam)": round(total_time, 2),
            "Biaya": round(cost),
            "Revenue": round(revenue),
            "Profit": round(profit)
        })

    total_biaya = total_fuel + total_operasional
    profit_total = total_revenue - total_biaya

    # Simpan ke CSV
    df = pd.DataFrame(laporan_csv)
    df.to_csv("laporan_cmvrp.csv", index=False)

    return render_template("laporan.html",
                           kendaraan_data=kendaraan_data,
                           total_fuel=round(total_fuel),
                           total_ops=round(total_operasional),
                           total_biaya=round(total_biaya),
                           total_revenue=round(total_revenue),
                           profit_total=round(profit_total))

@app.route('/laporan_rute')
def laporan_rute():
    depots, customers, rest_areas, menginap_locs = load_input_data()
    vehicle_count = load_vehicle_count()
    assignments = allocate_customers(customers, depots, vehicle_count)

    rute_kendaraan = []

    for i, vehicle in enumerate(assignments, start=1):
        customers_list = vehicle.get("customers", [])
        depot_nama, depot_data = vehicle.get("depot", ("Unknown", [0.0, 0.0]))
        depot_koordinat = depot_data

        if not customers_list:
            rute_kendaraan.append({
                "kendaraan": f"Kendaraan {i}",
                "rute": [],
                "kosong": True
            })
            continue

        route_coords, assigned_customers, overnight_stays, total_distance, total_revenue, total_cost, profit, total_service_time, total_rest_time, total_nginap_time, total_time, total_travel_time, total_work_time = tabu_search_vrp(
            depot_koordinat, customers_list, customers,
            rest_areas=rest_areas, menginap_locs=menginap_locs
        )

        assigned_dict = {tuple(coord): (name, round(serv_time, 2))
                         for coord, name, serv_time in assigned_customers}

        rute = []
        for pt in route_coords:
            row = {"lokasi": "", "aktivitas": "", "waktu_servis": ""}

            if isinstance(pt, tuple) and isinstance(pt[0], str):
                label, coord = pt
                coord = tuple(coord)
                if label == "rest":
                    nama = next((k for k, v in rest_areas.items() if tuple(v) == coord), "Virtual Rest Area")
                    row["lokasi"] = nama
                    row["aktivitas"] = "Istirahat"
                elif label == "nginap":
                    nama = next((k for k, v in menginap_locs.items() if tuple(v) == coord), "Virtual Menginap")
                    row["lokasi"] = nama
                    row["aktivitas"] = "Menginap"
            elif isinstance(pt, (tuple, list)) and len(pt) == 2:
                coord = tuple(pt)
                if coord in assigned_dict:
                    nama, service_time = assigned_dict[coord]
                    row["lokasi"] = nama
                    row["aktivitas"] = "Pelanggan"
                    row["waktu_servis"] = f"{service_time:.2f} jam"
                elif coord == tuple(depot_data[:2]):
                    row["lokasi"] = depot_nama
                    row["aktivitas"] = "Depot"

            if row["lokasi"]:
                rute.append(row)

        rute_kendaraan.append({
            "kendaraan": f"Kendaraan {i}",
            "rute": rute,
            "kosong": False,
            "waktu_pelayanan": round(total_service_time, 2),
            "waktu_istirahat": round(total_rest_time, 2),
            "waktu_nginap": round(total_nginap_time, 2),
            "total_waktu": round(total_time, 2),
            "waktu_perjalanan": round(total_travel_time),
            "total_work_time": round(total_work_time, 2)
        })

    return render_template("laporan_rute.html", rute_kendaraan=rute_kendaraan)

@app.route('/submit_rest_area', methods=['POST'])
def submit_rest_area():
    name = request.form['name']
    tipe = request.form['type']
    lat = float(request.form['lat'])
    lon = float(request.form['lon'])

    data = {
        "name": name,
        "type": tipe,
        "lat": lat,
        "lon": lon
    }

    if tipe == "customer":
        data["demand"] = request.form.get('demand', type=int)
        data["fee"] = request.form.get('fee', type=int)
    elif tipe == "depot":
        data["supply"] = request.form.get('supply', type=int)

    if not os.path.exists("data_lokasi.json"):
        with open("data_lokasi.json", "w") as f:
            json.dump([], f)

    with open("data_lokasi.json", "r+") as f:
        lokasi = json.load(f)
        lokasi.append(data)
        f.seek(0)
        json.dump(lokasi, f, indent=4)

    return redirect('/lokasi')

if __name__ == '__main__':
    app.run(debug=True)
