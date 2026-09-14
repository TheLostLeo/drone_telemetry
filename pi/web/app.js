/* ======================================================================================
   Drone Mission Control - Real-Time Dashboard App (app.js)
   ====================================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // 1. STATE & DOM ELEMENTS
  const el = {
    batV: document.getElementById('val-bat-v'),
    batA: document.getElementById('val-bat-a'),
    batW: document.getElementById('val-bat-w'),
    batPct: document.getElementById('val-bat-pct'),
    batBar: document.getElementById('bat-remaining-bar'),
    altRel: document.getElementById('val-alt-rel'),
    altMsl: document.getElementById('val-alt-msl'),
    climb: document.getElementById('val-climb'),
    heading: document.getElementById('val-heading'),
    headingCard: document.getElementById('val-heading-cardinal'),
    roll: document.getElementById('val-roll'),
    pitch: document.getElementById('val-pitch'),
    rssi: document.getElementById('val-rssi'),
    rssiBar: document.getElementById('rssi-bar'),
    sbcTemp: document.getElementById('val-sbc-temp'),
    sbcLoad: document.getElementById('val-sbc-load'),
    badgeArm: document.getElementById('badge-arm'),
    badgeMode: document.getElementById('badge-mode'),
    badgeMission: document.getElementById('badge-mission'),
    connIndicator: document.getElementById('conn-indicator'),
    connText: document.getElementById('conn-text'),
    gpsFix: document.getElementById('badge-gps-fix'),
    gpsSats: document.getElementById('badge-gps-sats'),
    gpsHdop: document.getElementById('badge-gps-hdop'),
    lat: document.getElementById('val-lat'),
    lon: document.getElementById('val-lon'),
    accX: document.getElementById('val-acc-x'),
    accY: document.getElementById('val-acc-y'),
    accZ: document.getElementById('val-acc-z'),
    cellDelta: document.getElementById('val-cell-delta'),
    errRoll: document.getElementById('val-err-roll'),
    errPitch: document.getElementById('val-err-pitch'),
    sbcTempTxt: document.getElementById('sbc-temp-txt'),
    sbcCpuTxt: document.getElementById('sbc-cpu-txt'),
    sbcRamTxt: document.getElementById('sbc-ram-txt'),
    sbcDiskTxt: document.getElementById('sbc-disk-txt'),
    sbcUptimeTxt: document.getElementById('sbc-uptime-txt')
  };

  const motors = [1, 2, 3, 4].map(i => ({
    pct: document.getElementById(`val-m${i}-pct`),
    bar: document.getElementById(`bar-m${i}`),
    pwm: document.getElementById(`val-m${i}-pwm`)
  }));

  const cells = [1, 2, 3, 4, 5, 6].map(i => ({
    val: document.getElementById(`val-cell-${i}`),
    bar: document.getElementById(`cell-bar-${i}`)
  }));

  let currentTelemetry = {};

  // 2. LEAFLET MAP INITIALIZATION
  let map, droneMarker, flightPathPolyline, searchGridBox;
  const flightHistory = [];
  const initialCoords = [12.971598, 77.594562];

  function initMap() {
    map = L.map('leaflet-map', {
      center: initialCoords,
      zoom: 18,
      zoomControl: true,
      attributionControl: false
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 20
    }).addTo(map);

    const droneIcon = L.divIcon({
      className: 'drone-leaflet-icon',
      html: `<div id="drone-map-svg" style="transform: rotate(0deg); transition: transform 0.1s linear;">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#00f0ff" stroke-width="2">
                <polygon points="12 2 19 21 12 17 5 21 12 2" fill="rgba(0, 240, 255, 0.4)"/>
              </svg>
             </div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    droneMarker = L.marker(initialCoords, { icon: droneIcon }).addTo(map);

    flightPathPolyline = L.polyline([], {
      color: '#00f0ff',
      weight: 3,
      opacity: 0.8,
      dashArray: '4, 6'
    }).addTo(map);

    searchGridBox = L.rectangle([
      [initialCoords[0] - 0.00045, initialCoords[1] - 0.00045],
      [initialCoords[0] + 0.00045, initialCoords[1] + 0.00045]
    ], {
      color: '#ffd000',
      weight: 2,
      fillColor: '#ffd000',
      fillOpacity: 0.08
    }).addTo(map);
  }

  initMap();

  document.getElementById('btn-recenter').addEventListener('click', () => {
    if (droneMarker) {
      map.panTo(droneMarker.getLatLng(), { animate: true });
    }
  });

  // 3. CHART.JS REAL-TIME CHARTS
  const maxDataPoints = 40;
  const timeLabels = Array(maxDataPoints).fill('');

  const gyroCtx = document.getElementById('gyroChart').getContext('2d');
  const gyroChart = new Chart(gyroCtx, {
    type: 'line',
    data: {
      labels: [...timeLabels],
      datasets: [
        { label: 'Roll Rate (ωx)', data: Array(maxDataPoints).fill(0), borderColor: '#00f0ff', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.2 },
        { label: 'Pitch Rate (ωy)', data: Array(maxDataPoints).fill(0), borderColor: '#ffd000', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.2 },
        { label: 'Yaw Rate (ωz)', data: Array(maxDataPoints).fill(0), borderColor: '#ff0077', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.2 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { grid: { color: '#1e293f' }, ticks: { color: '#8b9bb4', font: { size: 10 } } }
      }
    }
  });

  const pidCtx = document.getElementById('pidChart').getContext('2d');
  const pidChart = new Chart(pidCtx, {
    type: 'line',
    data: {
      labels: [...timeLabels],
      datasets: [
        { label: 'Target Pitch', data: Array(maxDataPoints).fill(0), borderColor: '#ffd000', borderWidth: 1.5, borderDash: [4, 4], pointRadius: 0, tension: 0.2 },
        { label: 'Measured Pitch', data: Array(maxDataPoints).fill(0), borderColor: '#00ff88', borderWidth: 2, pointRadius: 0, tension: 0.2 },
        { label: 'Target Roll', data: Array(maxDataPoints).fill(0), borderColor: '#00f0ff', borderWidth: 1.5, borderDash: [4, 4], pointRadius: 0, tension: 0.2 },
        { label: 'Measured Roll', data: Array(maxDataPoints).fill(0), borderColor: '#ff0077', borderWidth: 2, pointRadius: 0, tension: 0.2 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { grid: { color: '#1e293f' }, ticks: { color: '#8b9bb4', font: { size: 10 } } }
      }
    }
  });

  // 4. TELEMETRY DISPATCHER
  function updateTelemetry(data) {
    currentTelemetry = data;

    const v = (data.battery_voltage || 0).toFixed(2);
    const a = (data.battery_current || 0).toFixed(1);
    const w = (data.battery_voltage * data.battery_current).toFixed(0);
    const pct = data.battery_remaining || 0;

    el.batV.textContent = v;
    el.batA.textContent = a;
    el.batW.textContent = w;
    el.batPct.textContent = pct;
    el.batBar.style.width = `${pct}%`;

    el.altRel.textContent = (data.altitude_relative || 0).toFixed(1);
    el.altMsl.textContent = (data.altitude_msl || 0).toFixed(1);
    el.climb.textContent = (data.climb_rate >= 0 ? '+' : '') + (data.climb_rate || 0).toFixed(1);

    const hdg = Math.round(data.heading || 0);
    el.heading.textContent = hdg.toString().padStart(3, '0');
    el.headingCard.textContent = getCardinal(hdg);
    el.roll.textContent = (data.attitude_roll || 0).toFixed(1);
    el.pitch.textContent = (data.attitude_pitch || 0).toFixed(1);

    const rssi = data.rc_rssi || 0;
    el.rssi.textContent = rssi;
    el.rssiBar.style.width = `${rssi}%`;
    el.sbcTemp.textContent = (data.sbc?.cpu_temp_c || 48.0).toFixed(1);
    el.sbcLoad.textContent = Math.round(data.sbc?.cpu_load_percent || 0);

    if (data.armed) {
      el.badgeArm.textContent = 'ARMED';
      el.badgeArm.className = 'status-badge armed';
    } else {
      el.badgeArm.textContent = 'DISARMED';
      el.badgeArm.className = 'status-badge disarmed';
    }

    el.badgeMode.textContent = data.flight_mode || 'UNKNOWN';
    el.badgeMission.textContent = data.mission_state || 'STANDBY';

    el.gpsFix.textContent = data.gps_fix_type || '3D FIX';
    el.gpsSats.textContent = `${data.satellites || 0} SATS`;
    el.gpsHdop.textContent = `HDOP: ${(data.hdop || 1.0).toFixed(1)}`;

    if (data.latitude && data.longitude && data.latitude !== 0) {
      el.lat.textContent = data.latitude.toFixed(6);
      el.lon.textContent = data.longitude.toFixed(6);

      const newLatLng = [data.latitude, data.longitude];
      droneMarker.setLatLng(newLatLng);

      const svgEl = document.getElementById('drone-map-svg');
      if (svgEl) {
        svgEl.style.transform = `rotate(${hdg}deg)`;
      }

      flightHistory.push(newLatLng);
      if (flightHistory.length > 300) flightHistory.shift();
      flightPathPolyline.setLatLngs(flightHistory);
    }

    el.accX.textContent = (data.accel_x || 0).toFixed(2);
    el.accY.textContent = (data.accel_y || 0).toFixed(2);
    el.accZ.textContent = (data.accel_z || 1.0).toFixed(2);

    gyroChart.data.datasets[0].data.shift();
    gyroChart.data.datasets[0].data.push(data.gyro_x || 0);
    gyroChart.data.datasets[1].data.shift();
    gyroChart.data.datasets[1].data.push(data.gyro_y || 0);
    gyroChart.data.datasets[2].data.shift();
    gyroChart.data.datasets[2].data.push(data.gyro_z || 0);
    gyroChart.update();

    pidChart.data.datasets[0].data.shift();
    pidChart.data.datasets[0].data.push(data.target_pitch || 0);
    pidChart.data.datasets[1].data.shift();
    pidChart.data.datasets[1].data.push(data.attitude_pitch || 0);
    pidChart.data.datasets[2].data.shift();
    pidChart.data.datasets[2].data.push(data.target_roll || 0);
    pidChart.data.datasets[3].data.shift();
    pidChart.data.datasets[3].data.push(data.attitude_roll || 0);
    pidChart.update();

    el.errRoll.textContent = `${(data.error_roll || 0).toFixed(1)}°`;
    el.errPitch.textContent = `${(data.error_pitch || 0).toFixed(1)}°`;

    const cellVals = data.cell_voltages || [];
    cells.forEach((c, idx) => {
      const cv = cellVals[idx] || 0.0;
      if (cv > 1.0) {
        c.val.textContent = `${cv.toFixed(2)}V`;
        const pct = Math.max(0, Math.min(100, ((cv - 3.2) / 1.0) * 100));
        c.bar.style.width = `${pct}%`;
        c.bar.style.background = cv >= 3.7 ? 'var(--accent-green)' : (cv >= 3.5 ? 'var(--accent-yellow)' : 'var(--accent-red)');
      } else {
        c.val.textContent = '--.--';
        c.bar.style.width = '0%';
      }
    });

    const delta = data.cell_delta_mv || 0;
    el.cellDelta.textContent = `ΔV: ${delta} mV (${delta <= 30 ? 'BALANCED ✓' : 'UNBALANCED !'})`;
    el.cellDelta.style.color = delta <= 30 ? 'var(--accent-green)' : 'var(--accent-red)';

    const pwms = data.motor_pwm || [1000, 1000, 1000, 1000];
    const pcts = data.motor_percent || [0, 0, 0, 0];
    motors.forEach((m, idx) => {
      const p = pcts[idx] || 0;
      m.pct.textContent = `${p}%`;
      m.bar.style.height = `${p}%`;
      m.pwm.textContent = `${pwms[idx] || 1000}µs`;
    });

    if (data.sbc) {
      el.sbcTempTxt.innerHTML = `${data.sbc.cpu_temp_c.toFixed(1)} °C <span class="${data.sbc.cpu_temp_c > 75 ? 'badge-warn' : 'badge-ok'}">${data.sbc.cpu_temp_c > 75 ? 'HIGH' : 'NORMAL'}</span>`;
      el.sbcCpuTxt.textContent = `${data.sbc.cpu_load_percent.toFixed(1)} %`;
      el.sbcRamTxt.textContent = `${data.sbc.ram_used_mb} MB / ${data.sbc.ram_total_mb} MB (${data.sbc.ram_percent.toFixed(1)}%)`;
      el.sbcDiskTxt.textContent = `${data.sbc.disk_free_gb} GB (${data.sbc.disk_percent.toFixed(0)}% used)`;

      const hrs = Math.floor(data.sbc.uptime_seconds / 3600);
      const mins = Math.floor((data.sbc.uptime_seconds % 3600) / 60);
      el.sbcUptimeTxt.textContent = `${hrs}h ${mins}m`;
    }
  }

  function getCardinal(deg) {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    return directions[Math.round(deg / 45) % 8];
  }

  // 5. MODAL INTERACTION & GRID SEARCH TRIGGER
  const gridModal = document.getElementById('grid-modal');
  const btnOpenModal = document.getElementById('btn-open-grid-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const btnSubmitGrid = document.getElementById('btn-submit-grid');
  const centerSelect = document.getElementById('input-center-type');
  const customCoordsGroup = document.getElementById('custom-coords-group');
  const alertBox = document.getElementById('mission-alert-box');

  btnOpenModal.addEventListener('click', () => {
    gridModal.classList.remove('hidden');
    alertBox.classList.add('hidden');
  });

  const closeModal = () => gridModal.classList.add('hidden');
  btnCloseModal.addEventListener('click', closeModal);
  btnCancelModal.addEventListener('click', closeModal);

  centerSelect.addEventListener('change', () => {
    if (centerSelect.value === 'custom') {
      customCoordsGroup.classList.remove('hidden');
    } else {
      customCoordsGroup.classList.add('hidden');
    }
  });

  btnSubmitGrid.addEventListener('click', async () => {
    const radius = parseFloat(document.getElementById('input-radius').value) || 50;
    const altitude = parseFloat(document.getElementById('input-altitude').value) || 15;
    const spacing = parseFloat(document.getElementById('input-spacing').value) || 10;

    let lat = null;
    let lon = null;
    if (centerSelect.value === 'custom') {
      lat = parseFloat(document.getElementById('input-custom-lat').value);
      lon = parseFloat(document.getElementById('input-custom-lon').value);
    }

    alertBox.className = 'alert-box';
    alertBox.textContent = 'Uploading mission to Pixhawk...';
    alertBox.classList.remove('hidden');

    try {
      const res = await fetch('/api/mission/grid_search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ radius, altitude, spacing, lat, lon })
      });
      const resData = await res.json();
      if (res.ok && resData.status === 'success') {
        alertBox.className = 'alert-box success';
        alertBox.textContent = `✓ Mission Uploaded! Generated ${resData.waypoints_generated} grid waypoints.`;
        setTimeout(closeModal, 2000);
      } else {
        alertBox.className = 'alert-box error';
        alertBox.textContent = `Upload failed: ${resData.message || 'Error'}`;
      }
    } catch (e) {
      alertBox.className = 'alert-box error';
      alertBox.textContent = `Network error: ${e.message}`;
    }
  });

  // 6. WEBSOCKET & SSE CONNECTION
  let ws = null;

  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      el.connText.textContent = 'LIVE 10Hz WS';
      el.connIndicator.classList.add('online');
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        updateTelemetry(payload);
      } catch (err) {
        console.error('JSON parse error:', err);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onclose = () => {
      el.connText.textContent = 'CONNECTING...';
      el.connIndicator.classList.remove('online');
      setTimeout(connectWebSocket, 2000);
    };
  }

  setInterval(async () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      try {
        const res = await fetch('/api/telemetry');
        if (res.ok) {
          const data = await res.json();
          updateTelemetry(data);
          el.connText.textContent = 'REST POLLING';
          el.connIndicator.classList.add('online');
        }
      } catch (e) {}
    }
  }, 500);

  connectWebSocket();
});
