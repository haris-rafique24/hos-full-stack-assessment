import { useMemo, useState } from 'react'
import axios from 'axios'
import { MapContainer, Marker, Polyline, Popup, TileLayer } from 'react-leaflet'
import './App.css'

function App() {
  const apiBaseUrl =
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.PROD
      ? 'https://hos-full-stack-assessment-backend.vercel.app'
      : 'http://127.0.0.1:8000')
  const [form, setForm] = useState({
    current_location: 'Dallas, TX',
    pickup_location: 'New York, NY',
    dropoff_location: 'Alabama',
    current_cycle_used: '15',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const mapCenter = useMemo(() => {
    if (!result?.locations?.length) return [39.8283, -98.5795]
    const points = result.locations.map((l) => [l.lat, l.lon])
    const avgLat = points.reduce((sum, [lat]) => sum + lat, 0) / points.length
    const avgLon = points.reduce((sum, [, lon]) => sum + lon, 0) / points.length
    return [avgLat, avgLon]
  }, [result])

  const routePath = useMemo(() => {
    if (!result?.route_geojson?.coordinates) return []
    return result.route_geojson.coordinates.map(([lon, lat]) => [lat, lon])
  }, [result])

  const onChange = (event) => {
    const { name, value } = event.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await axios.post(`${apiBaseUrl}/api/plan-trip/`, {
        ...form,
        current_cycle_used: Number(form.current_cycle_used),
      })
      setResult(response.data)
    } catch (err) {
      setError(err?.response?.data?.error || 'Unable to generate trip plan.')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="header">
        <p className="eyebrow">Dispatch Planning Dashboard</p>
        <h1>HOS Trip Planner + ELD Log Generator</h1>
        <p>Built for FMCSA 70/8 property-carrying assumptions with 11/14/30 rules.</p>
      </header>

      <section className="card">
        <div className="section-head">
          <h2>Trip Inputs</h2>
          <span className="pill">Property-carrying</span>
        </div>
        <form onSubmit={onSubmit} className="form-grid">
          <label>
            Current location
            <input name="current_location" value={form.current_location} onChange={onChange} required />
          </label>
          <label>
            Pickup location
            <input name="pickup_location" value={form.pickup_location} onChange={onChange} required />
          </label>
          <label>
            Drop-off location
            <input name="dropoff_location" value={form.dropoff_location} onChange={onChange} required />
          </label>
          <label>
            Current cycle used (hrs)
            <input
              type="number"
              min="0"
              max="70"
              step="0.25"
              name="current_cycle_used"
              value={form.current_cycle_used}
              onChange={onChange}
              required
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? 'Planning...' : 'Generate Route + Logs'}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <div className="section-head">
          <h2>Route Map</h2>
          <span className="pill muted">OpenStreetMap + OSRM</span>
        </div>
        <div className="map-wrap">
          <MapContainer center={mapCenter} zoom={5} scrollWheelZoom={true}>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {routePath.length > 0 && <Polyline positions={routePath} color="#3b82f6" />}
            {(result?.locations || []).map((point) => (
              <Marker key={`${point.type}-${point.lat}-${point.lon}`} position={[point.lat, point.lon]}>
                <Popup>
                  <strong>{point.type.toUpperCase()}</strong>
                  <br />
                  {point.name}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      </section>

      {result && (
        <>
          <section className="card summary">
            <div className="section-head">
              <h2>Trip Summary</h2>
              <span className="pill success">Plan Generated</span>
            </div>
            <div className="stats">
              <div>
                <span>Distance</span>
                <strong>{result.summary.distance_miles} mi</strong>
              </div>
              <div>
                <span>Driving Time</span>
                <strong>{result.summary.estimated_driving_hours} hrs</strong>
              </div>
              <div>
                <span>Total HOS Time</span>
                <strong>{result.summary.projected_total_hours_with_stops} hrs</strong>
              </div>
              <div>
                <span>Log Days Needed</span>
                <strong>{result.summary.days_required}</strong>
              </div>
              <div>
                <span>Cycle Used After Trip</span>
                <strong>{result.summary.cycle_used_after_trip} hrs</strong>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="section-head">
              <h2>Daily Log Sheets</h2>
            </div>
            <div className="legend">
              <span className="legend-item"><i className="swatch driving" />Driving</span>
              <span className="legend-item"><i className="swatch on_duty_not_driving" />On Duty (Not Driving)</span>
              <span className="legend-item"><i className="swatch off_duty" />Off Duty</span>
              <span className="legend-item"><i className="swatch sleeper_berth" />Sleeper Berth</span>
            </div>
            {result.daily_logs.map((day) => (
              <article key={day.date} className="log-day">
                <div className="log-day-head">
                  <h3>{day.date}</h3>
                  <span className="pill muted">24-hour record</span>
                </div>
                <div className="totals">
                  <span>Off Duty: {day.totals.off_duty}h</span>
                  <span>Sleeper: {day.totals.sleeper_berth}h</span>
                  <span>Driving: {day.totals.driving}h</span>
                  <span>On Duty (ND): {day.totals.on_duty_not_driving}h</span>
                </div>
                <div className="hour-ruler">
                  {Array.from({ length: 25 }).map((_, hour) => (
                    <span key={`hour-${day.date}-${hour}`}>{hour === 24 ? '24' : hour}</span>
                  ))}
                </div>
                <div className="timeline">
                  {day.segments.map((segment, index) => {
                    const width = `${((segment.end_hour - segment.start_hour) / 24) * 100}%`
                    return (
                      <div key={`${segment.label}-${index}`} className={`bar ${segment.status}`} style={{ width }}>
                        {segment.label}
                      </div>
                    )
                  })}
                </div>
              </article>
            ))}
          </section>
        </>
      )}
    </main>
  )
}

export default App
