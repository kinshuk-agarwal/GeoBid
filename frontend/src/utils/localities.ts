/** Well-known localities offered in map search (no external geocoder needed). */
export interface Locality {
  name: string
  latitude: number
  longitude: number
}

export const LOCALITIES: Locality[] = [
  { name: 'Kondapur', latitude: 17.4615, longitude: 78.364 },
  { name: 'HITEC City', latitude: 17.4504, longitude: 78.3809 },
  { name: 'Gachibowli', latitude: 17.4401, longitude: 78.3489 },
  { name: 'Madhapur', latitude: 17.4483, longitude: 78.3915 },
  { name: 'Financial District', latitude: 17.4180, longitude: 78.343 },
  { name: 'Kothaguda', latitude: 17.4609, longitude: 78.3713 },
  { name: 'Miyapur', latitude: 17.4968, longitude: 78.3577 },
  { name: 'Kukatpally (JNTU)', latitude: 17.4933, longitude: 78.3915 },
  { name: 'Raidurg', latitude: 17.43, longitude: 78.385 },
  { name: 'Nanakramguda', latitude: 17.419, longitude: 78.356 },
  { name: 'Jubilee Hills', latitude: 17.43, longitude: 78.408 },
  { name: 'Lingampally', latitude: 17.484, longitude: 78.317 },
]
