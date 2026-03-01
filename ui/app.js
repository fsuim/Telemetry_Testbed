(() => {
  const $ = (id) => document.getElementById(id);

  const els = {
    host: $('host'),
    port: $('port'),
    path: $('path'),
    dot: $('dot'),
    connLabel: $('connLabel'),
    lastMsg: $('lastMsg'),

    btnConnect: $('btnConnect'),
    btnDisconnect: $('btnDisconnect'),
    btnPause: $('btnPause'),

    lastN: $('lastN'),
    btnHistory: $('btnHistory'),
    btnClear: $('btnClear'),

    vRobot: $('vRobot'),
    vImu: $('vImu'),
    vTilt: $('vTilt'),
    vSeq: $('vSeq'),
    vStatus: $('vStatus'),
    vTime: $('vTime'),

    ax: $('ax'), ay: $('ay'), az: $('az'),
    gx: $('gx'), gy: $('gy'), gz: $('gz'),
    tx: $('tx'), ty: $('ty'), tz: $('tz'),

    tbody: $('tbody'),

    cAccel: $('cAccel'),
    cGyro: $('cGyro'),
    cTilt: $('cTilt'),

    // Motor elements are created dynamically (so index.html doesn't need edits)
    m1id: null, m1tics: null, m1rpm: null, m1temp: null, m1vps: null, m1cps: null,
    m2id: null, m2tics: null, m2rpm: null, m2temp: null, m2vps: null, m2cps: null,
    cM1Rpm: null, cM2Rpm: null,
  };

  const state = {
    ws: null,
    paused: false,
    samples: [],
    maxSamples: 500,

    accelMag: [],
    gyroMag: [],
    tiltX: [],

    m1Rpm: [],
    m2Rpm: [],

    maxSpark: 240,

    tableHasMotorCols: false,
  };

  function fmt(n, digits = 6) {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
    return n.toFixed(digits);
  }

  function fmtInt(n) {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
    return String(Math.trunc(n));
  }

  function fmtTime(tNs) {
    if (typeof tNs === 'number' && Number.isFinite(tNs)) {
      const ms = tNs / 1e6;
      const d = new Date(ms);
      return d.toLocaleString();
    }
    return '—';
  }

  function setConnStatus(kind, label) {
    els.dot.classList.remove('ok', 'warn');
    if (kind === 'ok') els.dot.classList.add('ok');
    else if (kind === 'warn') els.dot.classList.add('warn');
    els.connLabel.textContent = label;
  }

  function wsUrlFromInputs() {
    const host = (els.host.value || '').trim() || 'localhost';
    const port = String(els.port.value || '').trim() || '8080';
    let path = (els.path.value || '').trim() || '/';
    if (!path.startsWith('/')) path = '/' + path;
    return `ws://${host}:${port}${path}`;
  }

  function appendSpark(arr, v) {
    arr.push(v);
    if (arr.length > state.maxSpark) arr.splice(0, arr.length - state.maxSpark);
  }

  function drawSpark(canvas, arr) {
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = '#ffffff';
    ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
    ctx.globalAlpha = 1;

    if (!arr.length) return;

    let min = Infinity, max = -Infinity;
    for (const v of arr) {
      if (!Number.isFinite(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return;
    if (min === max) { min -= 1; max += 1; }

    const pad = 8;
    const xStep = (w - pad * 2) / Math.max(1, arr.length - 1);

    ctx.globalAlpha = 0.95;
    ctx.beginPath();
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      const x = pad + i * xStep;
      const y = pad + (1 - (v - min) / (max - min)) * (h - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.25;
    ctx.stroke();

    ctx.globalAlpha = 0.65;
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace';
    ctx.fillText(`${min.toFixed(2)} .. ${max.toFixed(2)}`, 10, 18);
    ctx.globalAlpha = 1;
  }

  function ensureMotorUI() {
    if (els.m1rpm && els.m2rpm) return; // already created

    const card = els.vRobot?.closest?.('section.card');
    if (!card) return;

    // In the original HTML there's an <hr> before "Buffer"
    const hr = card.querySelector('hr');
    if (!hr) return;

    const wrap = document.createElement('div');
    wrap.id = 'motorsPanel';
    wrap.style.marginTop = '12px';

    wrap.innerHTML = `
      <h2>Motores</h2>
      <div class="sensorGrid">
        <div>
          <h2 style="margin-top:0;">Motor 1</h2>
          <div class="triple">
            <div class="val"><div class="t">rpm</div><div id="m1rpm" class="n">—</div></div>
            <div class="val"><div class="t">temperatura (°C)</div><div id="m1temp" class="n">—</div></div>
            <div class="val"><div class="t">tics</div><div id="m1tics" class="n">—</div></div>
          </div>
          <div class="triple" style="margin-top:8px;">
            <div class="val"><div class="t">voltage (mV)</div><div id="m1vps" class="n">—</div></div>
            <div class="val"><div class="t">current (mA)</div><div id="m1cps" class="n">—</div></div>
            <div class="val"><div class="t">motor_id</div><div id="m1id" class="n">—</div></div>
          </div>

          <div style="margin-top:10px;">
            <label>Motor1 rpm (sparkline)</label>
            <canvas id="cM1Rpm" width="600" height="140"></canvas>
          </div>
        </div>

        <div>
          <h2 style="margin-top:0;">Motor 2</h2>
          <div class="triple">
            <div class="val"><div class="t">rpm</div><div id="m2rpm" class="n">—</div></div>
            <div class="val"><div class="t">temperatura (°C)</div><div id="m2temp" class="n">—</div></div>
            <div class="val"><div class="t">tics</div><div id="m2tics" class="n">—</div></div>
          </div>
          <div class="triple" style="margin-top:8px;">
            <div class="val"><div class="t">voltage (mV)</div><div id="m2vps" class="n">—</div></div>
            <div class="val"><div class="t">current (mA)</div><div id="m2cps" class="n">—</div></div>
            <div class="val"><div class="t">motor_id</div><div id="m2id" class="n">—</div></div>
          </div>

          <div style="margin-top:10px;">
            <label>Motor2 rpm (sparkline)</label>
            <canvas id="cM2Rpm" width="600" height="140"></canvas>
          </div>
        </div>
      </div>
    `;

    card.insertBefore(wrap, hr);

    // cache refs
    els.m1id = $('m1id');
    els.m1tics = $('m1tics');
    els.m1rpm = $('m1rpm');
    els.m1temp = $('m1temp');
    els.m1vps = $('m1vps');
    els.m1cps = $('m1cps');

    els.m2id = $('m2id');
    els.m2tics = $('m2tics');
    els.m2rpm = $('m2rpm');
    els.m2temp = $('m2temp');
    els.m2vps = $('m2vps');
    els.m2cps = $('m2cps');

    els.cM1Rpm = $('cM1Rpm');
    els.cM2Rpm = $('cM2Rpm');
  }

  function ensureMotorColsInTable() {
    if (state.tableHasMotorCols) return;

    const table = els.tbody?.closest?.('table');
    if (!table) return;

    const headRow = table.querySelector('thead tr');
    if (!headRow) return;

    const ths = Array.from(headRow.querySelectorAll('th'));
    const already = ths.some(th => (th.textContent || '').toLowerCase().includes('m1 rpm'));
    if (already) {
      state.tableHasMotorCols = true;
      return;
    }

    // Insert before tilt_status column if it exists
    let tiltIdx = ths.findIndex(th => (th.textContent || '').trim() === 'tilt_status');
    if (tiltIdx < 0) tiltIdx = ths.length - 1;

    const labels = ['m1 rpm', 'm1 temp', 'm2 rpm', 'm2 temp'];
    for (let i = 0; i < labels.length; i++) {
      const th = document.createElement('th');
      th.textContent = labels[i];
      const ref = headRow.children[tiltIdx + i] || null;
      headRow.insertBefore(th, ref);
    }

    state.tableHasMotorCols = true;
  }

  function renderLatest(s) {
    ensureMotorUI();

    els.vRobot.textContent = s.robot_id ?? '—';
    els.vImu.textContent = s.imu_id ?? '—';
    els.vTilt.textContent = s.tilt_id ?? '—';
    els.vSeq.textContent = (s.seq ?? '—');
    els.vStatus.textContent = (s.tilt_status ?? '—');
    els.vTime.textContent = fmtTime(s.t_ns);

    const acc = s.accel || {};
    const gyr = s.gyro || {};
    const tilt = s.tilt || {};

    els.ax.textContent = fmt(Number(acc.x));
    els.ay.textContent = fmt(Number(acc.y));
    els.az.textContent = fmt(Number(acc.z));

    els.gx.textContent = fmt(Number(gyr.x));
    els.gy.textContent = fmt(Number(gyr.y));
    els.gz.textContent = fmt(Number(gyr.z));

    els.tx.textContent = fmt(Number(tilt.x));
    els.ty.textContent = fmt(Number(tilt.y));
    els.tz.textContent = fmt(Number(tilt.z));

    const ax = Number(acc.x), ay = Number(acc.y), az = Number(acc.z);
    const gx = Number(gyr.x), gy = Number(gyr.y), gz = Number(gyr.z);
    const tx = Number(tilt.x);

    const accMag = Number.isFinite(ax) && Number.isFinite(ay) && Number.isFinite(az)
      ? Math.sqrt(ax*ax + ay*ay + az*az)
      : NaN;
    const gyrMag = Number.isFinite(gx) && Number.isFinite(gy) && Number.isFinite(gz)
      ? Math.sqrt(gx*gx + gy*gy + gz*gz)
      : NaN;

    appendSpark(state.accelMag, accMag);
    appendSpark(state.gyroMag, gyrMag);
    appendSpark(state.tiltX, tx);

    drawSpark(els.cAccel, state.accelMag);
    drawSpark(els.cGyro, state.gyroMag);
    drawSpark(els.cTilt, state.tiltX);

    // motors (may be missing for older data)
    const motors = s.motors || {};
    const m1 = motors.motor1 || {};
    const m2 = motors.motor2 || {};

    const m1rpm = Number(m1.rpm);
    const m2rpm = Number(m2.rpm);

    if (els.m1id) els.m1id.textContent = m1.id ?? '—';
    if (els.m1tics) els.m1tics.textContent = fmtInt(Number(m1.tics));
    if (els.m1rpm) els.m1rpm.textContent = fmtInt(m1rpm);
    if (els.m1temp) els.m1temp.textContent = fmtInt(Number(m1.temperature_c));
    if (els.m1vps) els.m1vps.textContent = fmtInt(Number(m1.voltage_power_stage_mv));
    if (els.m1cps) els.m1cps.textContent = fmtInt(Number(m1.current_power_stage_ma));

    if (els.m2id) els.m2id.textContent = m2.id ?? '—';
    if (els.m2tics) els.m2tics.textContent = fmtInt(Number(m2.tics));
    if (els.m2rpm) els.m2rpm.textContent = fmtInt(m2rpm);
    if (els.m2temp) els.m2temp.textContent = fmtInt(Number(m2.temperature_c));
    if (els.m2vps) els.m2vps.textContent = fmtInt(Number(m2.voltage_power_stage_mv));
    if (els.m2cps) els.m2cps.textContent = fmtInt(Number(m2.current_power_stage_ma));

    appendSpark(state.m1Rpm, Number.isFinite(m1rpm) ? m1rpm : NaN);
    appendSpark(state.m2Rpm, Number.isFinite(m2rpm) ? m2rpm : NaN);

    drawSpark(els.cM1Rpm, state.m1Rpm);
    drawSpark(els.cM2Rpm, state.m2Rpm);
  }

  function pushSample(s) {
    state.samples.push(s);
    if (state.samples.length > state.maxSamples) {
      state.samples.splice(0, state.samples.length - state.maxSamples);
    }
  }

  function renderTable() {
    ensureMotorColsInTable();

    const rows = [];
    const take = 40;
    const start = Math.max(0, state.samples.length - take);
    for (let i = start; i < state.samples.length; i++) {
      const s = state.samples[i];
      const acc = s.accel || {};
      const gyr = s.gyro || {};
      const tilt = s.tilt || {};

      const motors = s.motors || {};
      const m1 = motors.motor1 || {};
      const m2 = motors.motor2 || {};

      const t = (typeof s.t === 'number' && Number.isFinite(s.t)) ? s.t.toFixed(3) : '—';
      const ids = `${s.robot_id ?? ''}/${s.imu_id ?? ''}/${s.tilt_id ?? ''}`;

      rows.push(
        `<tr>` +
          `<td>${t}</td>` +
          `<td>${s.seq ?? ''}</td>` +
          `<td>${fmt(Number(acc.x),3)}, ${fmt(Number(acc.y),3)}, ${fmt(Number(acc.z),3)}</td>` +
          `<td>${fmt(Number(gyr.x),3)}, ${fmt(Number(gyr.y),3)}, ${fmt(Number(gyr.z),3)}</td>` +
          `<td>${fmt(Number(tilt.x),3)}, ${fmt(Number(tilt.y),3)}, ${fmt(Number(tilt.z),3)}</td>` +
          `<td>${fmtInt(Number(m1.rpm))}</td>` +
          `<td>${fmtInt(Number(m1.temperature_c))}</td>` +
          `<td>${fmtInt(Number(m2.rpm))}</td>` +
          `<td>${fmtInt(Number(m2.temperature_c))}</td>` +
          `<td>${s.tilt_status ?? ''}</td>` +
          `<td>${ids}</td>` +
        `</tr>`
      );
    }
    els.tbody.innerHTML = rows.join('');
  }

  function handleTelemetry(msg) {
    if (state.paused) return;
    pushSample(msg);
    renderLatest(msg);
    renderTable();
  }

  function handleHistory(msg) {
    if (!Array.isArray(msg.items)) return;
    for (const item of msg.items) {
      if (!item || item.type !== 'telemetry') continue;
      pushSample(item);
    }
    if (!state.paused && state.samples.length) {
      renderLatest(state.samples[state.samples.length - 1]);
    }
    renderTable();
  }

  function connect() {
    disconnect();

    const url = wsUrlFromInputs();
    setConnStatus('warn', 'conectando...');

    let ws;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      setConnStatus('', 'falha ao criar WebSocket');
      console.error(e);
      return;
    }

    state.ws = ws;

    ws.onopen = () => {
      setConnStatus('ok', 'conectado');
      els.btnConnect.disabled = true;
      els.btnDisconnect.disabled = false;
      els.btnPause.disabled = false;
      els.btnHistory.disabled = false;
      requestHistory();
    };

    ws.onclose = () => {
      setConnStatus('', 'desconectado');
      els.btnConnect.disabled = false;
      els.btnDisconnect.disabled = true;
      els.btnPause.disabled = true;
      els.btnHistory.disabled = true;
    };

    ws.onerror = (ev) => {
      console.warn('ws error', ev);
      setConnStatus('', 'erro');
    };

    ws.onmessage = (ev) => {
      els.lastMsg.textContent = new Date().toLocaleTimeString();
      const txt = typeof ev.data === 'string' ? ev.data : '';
      let msg;
      try { msg = JSON.parse(txt); } catch { return; }

      if (!msg || typeof msg.type !== 'string') return;
      if (msg.type === 'status') {
        if (msg.status === 'online') setConnStatus('ok', 'conectado');
      } else if (msg.type === 'telemetry') {
        handleTelemetry(msg);
      } else if (msg.type === 'history') {
        handleHistory(msg);
      } else if (msg.type === 'error') {
        console.warn('server error:', msg);
      }
    };
  }

  function disconnect() {
    if (state.ws) {
      try { state.ws.close(); } catch {}
      state.ws = null;
    }
  }

  function requestHistory() {
    const ws = state.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const n = Math.max(1, Math.min(5000, Number(els.lastN.value || 300)));
    ws.send(JSON.stringify({ type: 'history', last: n }));
  }

  function clearAll() {
    state.samples = [];
    state.accelMag = [];
    state.gyroMag = [];
    state.tiltX = [];
    state.m1Rpm = [];
    state.m2Rpm = [];

    els.tbody.innerHTML = '';

    for (const id of ['vRobot','vImu','vTilt','vSeq','vStatus','vTime','ax','ay','az','gx','gy','gz','tx','ty','tz']) {
      const el = $(id);
      if (el) el.textContent = '—';
    }

    for (const id of ['m1id','m1tics','m1rpm','m1temp','m1vps','m1cps','m2id','m2tics','m2rpm','m2temp','m2vps','m2cps']) {
      const el = $(id);
      if (el) el.textContent = '—';
    }

    drawSpark(els.cAccel, []);
    drawSpark(els.cGyro, []);
    drawSpark(els.cTilt, []);
    drawSpark(els.cM1Rpm, []);
    drawSpark(els.cM2Rpm, []);
  }

  function togglePause() {
    state.paused = !state.paused;
    els.btnPause.textContent = state.paused ? 'Retomar' : 'Pausar';
    els.btnPause.classList.toggle('primary', state.paused);
    els.btnPause.classList.toggle('warn', !state.paused);
  }

  function initDefaults() {
    const host = (location.hostname && location.hostname.length) ? location.hostname : 'localhost';
    els.host.value = host;
    els.port.value = '8080';
    els.path.value = '/';
  }

  // Hook UI
  els.btnConnect.addEventListener('click', connect);
  els.btnDisconnect.addEventListener('click', () => { disconnect(); });
  els.btnHistory.addEventListener('click', requestHistory);
  els.btnClear.addEventListener('click', clearAll);
  els.btnPause.addEventListener('click', togglePause);

  initDefaults();
  setConnStatus('', 'desconectado');

  // create motor UI immediately (if possible)
  ensureMotorUI();
  ensureMotorColsInTable();
})();