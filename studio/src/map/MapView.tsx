import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const STYLE_LIGHT = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const STYLE_DARK = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

type LayerKey = 'corridors' | 'generators' | 'dc'

const DATA = `${import.meta.env.BASE_URL}data`

export function MapView({ theme }: { theme: 'light' | 'dark' }) {
  const holder = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    corridors: true,
    generators: true,
    dc: true,
  })
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!holder.current) return
    const m = new maplibregl.Map({
      container: holder.current,
      style: theme === 'dark' ? STYLE_DARK : STYLE_LIGHT,
      center: [122.5, 12.2],
      zoom: 5.1,
      attributionControl: { compact: true },
    })
    map.current = m
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    m.on('load', async () => {
      const [ck, gen, dc] = await Promise.all([
        fetch(`${DATA}/chokepoints.geojson`).then((r) => r.json()),
        fetch(`${DATA}/generators.geojson`).then((r) => r.json()),
        fetch(`${DATA}/dc_sites.geojson`).then((r) => r.json()),
      ])
      m.addSource('ck', { type: 'geojson', data: ck })
      m.addLayer({
        id: 'ck-line',
        type: 'line',
        source: 'ck',
        paint: { 'line-color': '#b3261e', 'line-width': 2.4, 'line-dasharray': [2, 1] },
      })
      m.addSource('gen', { type: 'geojson', data: gen })
      m.addLayer({
        id: 'gen-pt',
        type: 'circle',
        source: 'gen',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['get', 'capacity_mw'],
            200,
            5,
            1340,
            14,
          ],
          'circle-color': [
            'match',
            ['get', 'fuel'],
            'natural_gas',
            '#2563eb',
            'coal',
            '#64748b',
            '#64748b',
          ],
          'circle-opacity': 0.85,
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 1,
        },
      })
      m.addSource('dc', { type: 'geojson', data: dc })
      m.addLayer({
        id: 'dc-pt',
        type: 'circle',
        source: 'dc',
        paint: {
          'circle-radius': 5,
          'circle-color': '#b45309',
          'circle-opacity': 0.9,
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 1,
        },
      })
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: true })
      const bind = (id: string, html: (p: Record<string, unknown>) => string) => {
        m.on('mouseenter', id, () => (m.getCanvas().style.cursor = 'pointer'))
        m.on('mouseleave', id, () => {
          m.getCanvas().style.cursor = ''
          pop.remove()
        })
        m.on('click', id, (e) => {
          const f = e.features?.[0]
          if (!f) return
          const g = f.geometry as { coordinates: [number, number] }
          pop
            .setLngLat(g.coordinates)
            .setHTML(html(f.properties as Record<string, unknown>))
            .addTo(m)
        })
      }
      bind(
        'gen-pt',
        (p) =>
          `<b>${p.name}</b><br>${p.capacity_mw} MW · ${String(p.fuel).replace('_', ' ')}<br><span class="pop-muted">${p.owner}</span>`
      )
      bind('dc-pt', (p) => `<b>${p.name}</b><br>${p.mw ?? '?'} MW · ${p.status}`)
      bind('ck-line', (p) => `<b>${p.name}</b><br>${p.evidence ?? ''}`)
      setReady(true)
    })
    return () => m.remove()
  }, [theme])

  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    const vis = (id: string, on: boolean) =>
      m.getLayer(id) && m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    vis('ck-line', layers.corridors)
    vis('gen-pt', layers.generators)
    vis('dc-pt', layers.dc)
  }, [layers, ready])

  const toggles: { key: LayerKey; label: string; swatch: string }[] = [
    { key: 'corridors', label: 'HVDC corridors', swatch: '#b3261e' },
    { key: 'generators', label: 'Named generators', swatch: '#64748b' },
    { key: 'dc', label: 'Data centers', swatch: '#b45309' },
  ]

  return (
    <div className="mapview">
      <div ref={holder} className="mapview__canvas" />
      <div className="mapview__legend" role="group" aria-label="Map layers">
        <div className="mapview__legendhead">Network</div>
        {toggles.map((t) => (
          <label className="maptoggle" key={t.key}>
            <input
              type="checkbox"
              checked={layers[t.key]}
              onChange={(e) => setLayers((s) => ({ ...s, [t.key]: e.target.checked }))}
            />
            <i style={{ background: t.swatch }} />
            {t.label}
          </label>
        ))}
        <p className="mapview__note">
          Corridors schematic. Generator and data-center pins are city-precision.
        </p>
      </div>
    </div>
  )
}
