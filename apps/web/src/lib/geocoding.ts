export const GUJARAT_CITIES = [
  // Major Cities
  { name: 'Ahmedabad', lat: 23.0225, lon: 72.5714 },
  { name: 'Surat', lat: 21.1702, lon: 72.8311 },
  { name: 'Vadodara', lat: 22.3072, lon: 73.1812 },
  { name: 'Rajkot', lat: 22.3039, lon: 70.8022 },
  { name: 'Gandhinagar', lat: 23.2156, lon: 72.6369 },
  
  // Mid-tier & Regional Hubs
  { name: 'Bhavnagar', lat: 21.7645, lon: 72.1519 },
  { name: 'Jamnagar', lat: 22.4707, lon: 70.0577 },
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
  { name: 'Surendranagar', lat: 22.7284, lon: 71.6371 },

  // Ahmedabad Localities / Suburbs
  { name: 'Sanand', lat: 22.9866, lon: 72.3831 },
  { name: 'Bopal', lat: 23.0298, lon: 72.4646 },
  { name: 'Satellite', lat: 23.0270, lon: 72.5188 },
  { name: 'Vastrapur', lat: 23.0371, lon: 72.5273 },
  { name: 'Dharamnagar', lat: 23.0673, lon: 72.5936 }, // Near Sabarmati
  { name: 'Maninagar', lat: 22.9972, lon: 72.6053 },
  { name: 'Naroda', lat: 23.0664, lon: 72.6534 },
  { name: 'Gota', lat: 23.0906, lon: 72.5332 },
  { name: 'Thaltej', lat: 23.0487, lon: 72.5085 },
  { name: 'SG Highway', lat: 23.0336, lon: 72.5126 },
  { name: 'Prahlad Nagar', lat: 23.0116, lon: 72.5028 },
  { name: 'Vatva', lat: 22.9669, lon: 72.6078 },
  { name: 'Chandkheda', lat: 23.1118, lon: 72.5807 },
  { name: 'Motera', lat: 23.0991, lon: 72.5925 },
  
  // Surat Localities
  { name: 'Adajan', lat: 21.1959, lon: 72.7933 },
  { name: 'Piplod', lat: 21.1578, lon: 72.7758 },
  { name: 'Vesu', lat: 21.1418, lon: 72.7725 },
  { name: 'Katargam', lat: 21.2266, lon: 72.8222 },
  { name: 'Varachha', lat: 21.2185, lon: 72.8647 },
  { name: 'Palsana', lat: 21.0833, lon: 72.9667 },
  { name: 'Sachin', lat: 21.0828, lon: 72.8427 },
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
