from math import asin, cos, radians, sin, sqrt


def distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    """Return great-circle distance in kilometres between two coordinate pairs."""
    lat_a, lon_a, lat_b, lon_b = map(radians, (float(latitude_a), float(longitude_a), float(latitude_b), float(longitude_b)))
    d_lat = lat_b - lat_a
    d_lon = lon_b - lon_a
    haversine = sin(d_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(d_lon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1, haversine)))
