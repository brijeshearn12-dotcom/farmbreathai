import csv
import os

districts = [
    # ===== PUNJAB (23 districts) =====
    {"district_name": "Amritsar", "state": "Punjab", "latitude": 31.63, "longitude": 74.87, "total_area_km2": 2647, "major_crop": "Rice-Wheat"},
    {"district_name": "Barnala", "state": "Punjab", "latitude": 30.38, "longitude": 75.55, "total_area_km2": 1411, "major_crop": "Rice-Wheat"},
    {"district_name": "Bathinda", "state": "Punjab", "latitude": 30.21, "longitude": 74.95, "total_area_km2": 3344, "major_crop": "Cotton-Wheat"},
    {"district_name": "Faridkot", "state": "Punjab", "latitude": 30.67, "longitude": 74.75, "total_area_km2": 1472, "major_crop": "Rice-Wheat"},
    {"district_name": "Fatehgarh Sahib", "state": "Punjab", "latitude": 30.64, "longitude": 76.39, "total_area_km2": 1180, "major_crop": "Rice-Wheat"},
    {"district_name": "Fazilka", "state": "Punjab", "latitude": 30.40, "longitude": 74.03, "total_area_km2": 3113, "major_crop": "Cotton-Wheat"},
    {"district_name": "Ferozepur", "state": "Punjab", "latitude": 30.93, "longitude": 74.61, "total_area_km2": 2190, "major_crop": "Rice-Wheat"},
    {"district_name": "Gurdaspur", "state": "Punjab", "latitude": 32.04, "longitude": 75.40, "total_area_km2": 3563, "major_crop": "Rice-Wheat"},
    {"district_name": "Hoshiarpur", "state": "Punjab", "latitude": 31.53, "longitude": 75.91, "total_area_km2": 3365, "major_crop": "Wheat-Maize"},
    {"district_name": "Jalandhar", "state": "Punjab", "latitude": 31.33, "longitude": 75.58, "total_area_km2": 2625, "major_crop": "Rice-Wheat"},
    {"district_name": "Kapurthala", "state": "Punjab", "latitude": 31.38, "longitude": 75.38, "total_area_km2": 1646, "major_crop": "Rice-Wheat"},
    {"district_name": "Ludhiana", "state": "Punjab", "latitude": 30.90, "longitude": 75.85, "total_area_km2": 3744, "major_crop": "Rice-Wheat"},
    {"district_name": "Mansa", "state": "Punjab", "latitude": 29.99, "longitude": 75.40, "total_area_km2": 2174, "major_crop": "Cotton-Wheat"},
    {"district_name": "Moga", "state": "Punjab", "latitude": 30.81, "longitude": 75.17, "total_area_km2": 2235, "major_crop": "Rice-Wheat"},
    {"district_name": "Sri Muktsar Sahib", "state": "Punjab", "latitude": 30.47, "longitude": 74.52, "total_area_km2": 2596, "major_crop": "Cotton-Wheat"},
    {"district_name": "Pathankot", "state": "Punjab", "latitude": 32.27, "longitude": 75.65, "total_area_km2": 929, "major_crop": "Rice-Wheat"},
    {"district_name": "Patiala", "state": "Punjab", "latitude": 30.34, "longitude": 76.39, "total_area_km2": 3175, "major_crop": "Rice-Wheat"},
    {"district_name": "Rupnagar", "state": "Punjab", "latitude": 30.97, "longitude": 76.53, "total_area_km2": 1422, "major_crop": "Rice-Wheat"},
    {"district_name": "S.A.S. Nagar (Mohali)", "state": "Punjab", "latitude": 30.70, "longitude": 76.72, "total_area_km2": 1109, "major_crop": "Rice-Wheat"},
    {"district_name": "Sangrur", "state": "Punjab", "latitude": 30.25, "longitude": 75.84, "total_area_km2": 3685, "major_crop": "Rice-Wheat"},
    {"district_name": "Shahid Bhagat Singh Nagar", "state": "Punjab", "latitude": 31.10, "longitude": 76.16, "total_area_km2": 1283, "major_crop": "Rice-Wheat"},
    {"district_name": "Tarn Taran", "state": "Punjab", "latitude": 31.45, "longitude": 74.92, "total_area_km2": 2417, "major_crop": "Rice-Wheat"},
    {"district_name": "Malerkotla", "state": "Punjab", "latitude": 30.53, "longitude": 75.88, "total_area_km2": 410, "major_crop": "Rice-Wheat"},

    # ===== HARYANA (22 districts) =====
    {"district_name": "Ambala", "state": "Haryana", "latitude": 30.38, "longitude": 76.78, "total_area_km2": 1574, "major_crop": "Rice-Wheat"},
    {"district_name": "Bhiwani", "state": "Haryana", "latitude": 28.79, "longitude": 76.14, "total_area_km2": 5099, "major_crop": "Cotton-Wheat"},
    {"district_name": "Charkhi Dadri", "state": "Haryana", "latitude": 28.59, "longitude": 76.27, "total_area_km2": 1370, "major_crop": "Cotton-Wheat"},
    {"district_name": "Faridabad", "state": "Haryana", "latitude": 28.41, "longitude": 77.31, "total_area_km2": 783, "major_crop": "Wheat-Vegetables"},
    {"district_name": "Fatehabad", "state": "Haryana", "latitude": 29.51, "longitude": 75.45, "total_area_km2": 2538, "major_crop": "Cotton-Wheat"},
    {"district_name": "Gurugram", "state": "Haryana", "latitude": 28.46, "longitude": 77.03, "total_area_km2": 1258, "major_crop": "Wheat-Bajra"},
    {"district_name": "Hisar", "state": "Haryana", "latitude": 29.15, "longitude": 75.72, "total_area_km2": 3983, "major_crop": "Cotton-Wheat"},
    {"district_name": "Jhajjar", "state": "Haryana", "latitude": 28.61, "longitude": 76.66, "total_area_km2": 1834, "major_crop": "Wheat-Mustard"},
    {"district_name": "Jind", "state": "Haryana", "latitude": 29.32, "longitude": 76.31, "total_area_km2": 2702, "major_crop": "Rice-Wheat"},
    {"district_name": "Kaithal", "state": "Haryana", "latitude": 29.80, "longitude": 76.40, "total_area_km2": 2317, "major_crop": "Rice-Wheat"},
    {"district_name": "Karnal", "state": "Haryana", "latitude": 29.68, "longitude": 76.99, "total_area_km2": 2520, "major_crop": "Rice-Wheat"},
    {"district_name": "Kurukshetra", "state": "Haryana", "latitude": 29.97, "longitude": 76.88, "total_area_km2": 1530, "major_crop": "Rice-Wheat"},
    {"district_name": "Mahendragarh", "state": "Haryana", "latitude": 28.28, "longitude": 76.15, "total_area_km2": 1859, "major_crop": "Wheat-Bajra"},
    {"district_name": "Nuh", "state": "Haryana", "latitude": 28.10, "longitude": 77.00, "total_area_km2": 1874, "major_crop": "Wheat-Bajra"},
    {"district_name": "Palwal", "state": "Haryana", "latitude": 28.14, "longitude": 77.33, "total_area_km2": 1359, "major_crop": "Rice-Wheat"},
    {"district_name": "Panchkula", "state": "Haryana", "latitude": 30.69, "longitude": 76.85, "total_area_km2": 898, "major_crop": "Wheat-Maize"},
    {"district_name": "Panipat", "state": "Haryana", "latitude": 29.39, "longitude": 76.97, "total_area_km2": 1268, "major_crop": "Rice-Wheat"},
    {"district_name": "Rewari", "state": "Haryana", "latitude": 28.20, "longitude": 76.62, "total_area_km2": 1582, "major_crop": "Wheat-Bajra"},
    {"district_name": "Rohtak", "state": "Haryana", "latitude": 28.90, "longitude": 76.57, "total_area_km2": 1745, "major_crop": "Rice-Wheat"},
    {"district_name": "Sirsa", "state": "Haryana", "latitude": 29.53, "longitude": 75.03, "total_area_km2": 4277, "major_crop": "Cotton-Wheat"},
    {"district_name": "Sonipat", "state": "Haryana", "latitude": 28.99, "longitude": 77.02, "total_area_km2": 2122, "major_crop": "Rice-Wheat"},
    {"district_name": "Yamunanagar", "state": "Haryana", "latitude": 30.13, "longitude": 77.28, "total_area_km2": 1768, "major_crop": "Rice-Wheat"},

    # ===== UTTAR PRADESH (Top 15 stubble-burning districts) =====
    {"district_name": "Shahjahanpur", "state": "Uttar Pradesh", "latitude": 27.88, "longitude": 79.91, "total_area_km2": 4575, "major_crop": "Rice-Wheat"},
    {"district_name": "Hardoi", "state": "Uttar Pradesh", "latitude": 27.42, "longitude": 80.13, "total_area_km2": 5986, "major_crop": "Rice-Wheat"},
    {"district_name": "Bareilly", "state": "Uttar Pradesh", "latitude": 28.36, "longitude": 79.43, "total_area_km2": 4120, "major_crop": "Rice-Wheat"},
    {"district_name": "Sitapur", "state": "Uttar Pradesh", "latitude": 27.57, "longitude": 80.68, "total_area_km2": 5743, "major_crop": "Rice-Wheat"},
    {"district_name": "Pilibhit", "state": "Uttar Pradesh", "latitude": 28.63, "longitude": 79.80, "total_area_km2": 3499, "major_crop": "Rice-Wheat-Sugarcane"},
    {"district_name": "Lakhimpur Kheri", "state": "Uttar Pradesh", "latitude": 27.95, "longitude": 80.78, "total_area_km2": 7680, "major_crop": "Rice-Wheat-Sugarcane"},
    {"district_name": "Etah", "state": "Uttar Pradesh", "latitude": 27.63, "longitude": 78.66, "total_area_km2": 2456, "major_crop": "Wheat-Bajra"},
    {"district_name": "Mainpuri", "state": "Uttar Pradesh", "latitude": 27.23, "longitude": 79.02, "total_area_km2": 2745, "major_crop": "Rice-Wheat"},
    {"district_name": "Firozabad", "state": "Uttar Pradesh", "latitude": 27.15, "longitude": 78.40, "total_area_km2": 2361, "major_crop": "Wheat-Bajra"},
    {"district_name": "Etawah", "state": "Uttar Pradesh", "latitude": 26.78, "longitude": 79.02, "total_area_km2": 2287, "major_crop": "Wheat-Bajra"},
    {"district_name": "Auraiya", "state": "Uttar Pradesh", "latitude": 26.46, "longitude": 79.51, "total_area_km2": 2052, "major_crop": "Rice-Wheat"},
    {"district_name": "Kanpur Dehat", "state": "Uttar Pradesh", "latitude": 26.43, "longitude": 79.99, "total_area_km2": 3021, "major_crop": "Rice-Wheat"},
    {"district_name": "Kannauj", "state": "Uttar Pradesh", "latitude": 27.05, "longitude": 79.92, "total_area_km2": 1996, "major_crop": "Rice-Wheat-Potato"},
    {"district_name": "Farrukhabad", "state": "Uttar Pradesh", "latitude": 27.39, "longitude": 79.58, "total_area_km2": 2231, "major_crop": "Rice-Wheat"},
    {"district_name": "Budaun", "state": "Uttar Pradesh", "latitude": 28.04, "longitude": 79.12, "total_area_km2": 4863, "major_crop": "Rice-Wheat-Sugarcane"},
]

# Save to CSV
os.makedirs("data", exist_ok=True)
output_path = os.path.join("data", "districts.csv")

fieldnames = ["district_name", "state", "latitude", "longitude", "total_area_km2", "major_crop"]

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(districts)

print(f"Districts file created: {len(districts)} total districts")