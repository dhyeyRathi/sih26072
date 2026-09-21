export const GUJARAT_CITIES = [
  { name: 'Ahmedabad', lat: 23.0225, lon: 72.5714 },
  { name: 'Surat', lat: 21.1702, lon: 72.8311 },
  { name: 'Vadodara', lat: 22.3072, lon: 73.1812 },
  { name: 'Rajkot', lat: 22.3039, lon: 70.8022 },
  { name: 'Bhavnagar', lat: 21.7645, lon: 72.1519 },
  { name: 'Jamnagar', lat: 22.4707, lon: 70.0577 },
  { name: 'Gandhinagar', lat: 23.2156, lon: 72.6369 },
  { name: 'Junagadh', lat: 21.5222, lon: 70.4579 },
  { name: 'Anand', lat: 22.5645, lon: 72.9289 },
  { name: 'Navsari', lat: 20.9467, lon: 72.9520 },
  { name: 'Morbi', lat: 22.8120, lon: 70.8320 },
  { name: 'Nadiad', lat: 22.6916, lon: 72.8634 },
  { name: 'Bharuch', lat: 21.7051, lon: 72.9959 },
  { name: 'Porbandar', lat: 21.6417, lon: 69.6293 },
  { name: 'Mehsana', lat: 23.5880, lon: 72.3693 },
  { name: 'Bhuj', lat: 23.2420, lon: 69.6669 },
  { name: 'Gandhidham', lat: 23.0753, lon: 70.1337 },
  { name: 'Patan', lat: 23.8493, lon: 72.1158 },
  { name: 'Vapi', lat: 20.3852, lon: 72.9115 },
  { name: 'Godhra', lat: 22.7739, lon: 73.6150 },
  { name: 'Kheda', lat: 22.7482, lon: 72.6842 },
  { name: 'Surendranagar', lat: 22.7284, lon: 71.6371 }
];

function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Radius of the Earth in km
  const dLat = (lat2 - lat1) * (Math.PI / 180);
  const dLon = (lon2 - lon1) * (Math.PI / 180);
  const a = 
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) * 
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function getNearestCity(lat: number, lon: number): string {
  if (lat === undefined || lon === undefined || isNaN(lat) || isNaN(lon)) return "Unknown";
  let minDistance = Infinity;
  let nearestCity = "Unknown";

  for (const city of GUJARAT_CITIES) {
    const distance = haversine(lat, lon, city.lat, city.lon);
    if (distance < minDistance) {
      minDistance = distance;
      nearestCity = city.name;
    }
  }

  if (minDistance > 100) {
    return nearestCity + ` (approx)`;
  }
  
  return nearestCity;
}
