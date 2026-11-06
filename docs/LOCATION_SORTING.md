# Nearby listing sort

Recipients and recovery partners can choose **Use my location** on the listings page. The browser requests location permission only after that action. The app sends the current coordinates in a same-origin POST request, computes great-circle distances to pickup pins, then returns listings in nearest-first order with distances rounded to whole kilometres. The visitor's coordinates are not saved in the database or URL.

Providers can capture a pickup pin in the listing form while at the collection point. Listing coordinates remain server-side; the listings page receives only an approximate distance label. Listings without pins follow pinned listings and retain area-based matching order. The exact address and pin remain private until a request is accepted.

Users can decline location access and continue browsing by area. Geolocation requires a secure browser context, such as HTTPS or localhost. No map or geocoding provider is used.
