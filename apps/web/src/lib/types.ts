export interface StormCell {
  cell_id: string;
  center_lat: number;
  center_lon: number;
  centroid_y?: number;
  centroid_x?: number;
  radius_cells?: number;
  max_reflectivity_dbz: number;
  area_sq_km: number;
  lightning_rate: number;
  movement_speed_kmh: number;
  movement_direction_deg: number;
  intensity: 'weak' | 'moderate' | 'strong' | 'severe';
  trend: 'intensifying' | 'steady' | 'weakening' | 'dissipating';
}

export interface Forecast {
  horizon_minutes: number;
  predicted_lat: number;
  predicted_lon: number;
  uncertainty_km: number;
  thunderstorm_probability: number;
  lightning_probability: number;
  confidence_score?: number;
  predicted_dbz?: number;
  affected_area_km2?: number;
}

export interface StormTrajectory {
  cell_id: string;
  current_lat: number;
  current_lon: number;
  speed_kmh: number;
  direction_deg: number;
  intensity: 'weak' | 'moderate' | 'strong' | 'severe';
  trend: 'intensifying' | 'steady' | 'weakening' | 'dissipating';
  forecasts: Forecast[];
  trajectory_coords: number[][];
  eta_ahmedabad_minutes?: number | null;
  averaging_samples?: number;
}

export interface RiskAssessment {
  cell_id: string;
  risk_level: 'low' | 'moderate' | 'high' | 'severe';
  thunderstorm_probability: number;
  lightning_probability: number;
  intensity: 'weak' | 'moderate' | 'strong' | 'severe';
  speed_kmh: number;
  direction_deg: number;
  trend: 'intensifying' | 'steady' | 'weakening' | 'dissipating';
  eta_minutes?: number;
  target?: { lat: number; lon: number };
}

export interface LightningStrike {
  lat: number;
  lon: number;
  timestamp: string;
  intensity_ka: number;
  cell_id: string;
}

export interface SourceHealth {
  status: 'live' | 'delayed' | 'stale' | 'offline';
  last_data_at: string | null;
  latency_ms: number | null;
  error: string | null;
}

export interface SystemHealth {
  sources: {
    radar: SourceHealth;
    satellite: SourceHealth;
    lightning: SourceHealth;
    aws: SourceHealth;
    nwp: SourceHealth;
  };
  model: {
    status: 'ready' | 'running' | 'failed';
    last_inference_at: string | null;
    inference_latency_ms: number | null;
    model_version: string;
  };
  overall: 'healthy' | 'warning' | 'degraded' | 'operational';
  checked_at: string;
}

export interface StormUpdatePayload {
  timestamp: string;
  storms: StormCell[];
  trajectories: StormTrajectory[];
  risks: RiskAssessment[];
  lightning: LightningStrike[];
  radar_summary: {
    max_reflectivity: number;
    mean_reflectivity: number;
    active_cells: number;
  };
  radar_points?: Array<{ lat: number; lon: number; dbz: number }>;
  exposure_summary?: {
    total_assets: number;
    critical_count: number;
    warning_count: number;
    watch_count: number;
    safe_count: number;
    composite_exposure_score: number;
    threatened_districts: string[];
    estimated_exposed_population: number;
  };
}
