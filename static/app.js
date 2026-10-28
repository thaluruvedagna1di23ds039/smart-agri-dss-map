(function () {
  const csrf = document.querySelector('meta[name="csrf"]').content;
  const map = L.map('map').setView([20.59, 78.96], 5); // India overview
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  let marker = null;
  const $ = (id) => document.getElementById(id);

  // Safe DOM helpers: all text goes through textContent (no innerHTML).
  function el(tag, text, cls) {
    const e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function fillTable(table, head, rows) {
    table.replaceChildren();
    if (head) {
      const tr = el('tr');
      head.forEach((h) => tr.appendChild(el('th', h)));
      table.appendChild(tr);
    }
    rows.forEach((r) => {
      const tr = el('tr');
      r.forEach((c) => tr.appendChild(el('td', c)));
      table.appendChild(tr);
    });
  }

  function render(r) {
    const i = r.inputs;
    fillTable($('t-inputs'), null, [
      ['Latitude, longitude', r.lat + ', ' + r.lon],
      ['Region', r.region],
      ['Mean temperature', i.temp + ' °C'],
      ['Annual rainfall', i.rain + ' mm'],
      ['Relative humidity', i.humidity + ' %'],
      ['Soil pH', i.ph],
      ['Soil nitrogen', i.nitrogen + ' g/kg'],
      ['Soil organic carbon', i.soc + ' g/kg'],
      ['Clay', i.clay + ' %'],
    ]);
    $('srcs').textContent = 'Weather: ' + r.sources.weather + ' | Soil: ' + r.sources.soil;

    $('best').textContent = 'Best-suited crop: ' + r.best_crop +
      ' (about ' + r.ranking[0].yield_t_ha + ' t/ha)';
    fillTable($('t-rank'), ['Crop', 'Suitability %', 'Model yield t/ha', 'Past yield t/ha (APY)'],
      r.ranking.map((x) => [x.crop, x.suitability_pct, x.yield_t_ha,
        x.hist_yield_t_ha === null ? 'n/a' : x.hist_yield_t_ha + ' (' + x.hist_level + ')']));

    const inter = $('inter');
    inter.replaceChildren();
    if (!r.intercrops.length) {
      inter.appendChild(el('p', 'No strong intercrop pairing found for ' + r.intercrop_main +
        ' at this location.', 'muted'));
    } else {
      r.intercrops.forEach((x) => {
        const d = el('div', null, 'pair');
        d.appendChild(el('strong', x.main + ' + ' + x.partner + '  (row ratio ' + x.ratio + ')'));
        d.appendChild(el('p', x.reason));
        d.appendChild(el('small', 'Combined suitability score: ' + x.combo_score + '%', 'muted'));
        inter.appendChild(d);
      });
    }

    const rot = $('rot');
    rot.replaceChildren();
    r.rotation.forEach((s) => {
      const li = el('li');
      li.appendChild(el('strong', s.crop));
      li.appendChild(document.createTextNode(' (' + s.family + (s.legume ? ', legume' : '') + ') - ' + s.reason));
      rot.appendChild(li);
    });

    const n = r.nutrients;
    $('nut-head').textContent = 'For ' + n.crop + ': nitrogen requirement ' +
      n.crop_n_requirement_kg_ha + ' kg/ha, net need after soil supply ~' +
      n.net_n_need_kg_ha + ' kg/ha. Recovery shown for ' + n.sources[0].rate_t_ha + ' t/ha application.';
    fillTable($('t-nut'), ['Source', 'N kg/ha', 'P2O5 kg/ha', 'K2O kg/ha', 'N need covered %'],
      n.sources.map((s) => [s.source, s.N_kg_ha, s.P2O5_kg_ha, s.K2O_kg_ha, s.n_offset_pct]));

    $('mdl').textContent = 'R² ' + r.model.r2 + ' on held-out ' + r.model.data_source;
    $('out').hidden = false;
  }

  map.on('click', async (e) => {
    const lat = e.latlng.lat, lon = e.latlng.lng;
    if (marker) marker.remove();
    marker = L.marker([lat, lon]).addTo(map);
    $('out').hidden = true;
    $('status').textContent = 'Fetching weather and soil data, then running the models...';
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({lat: lat, lon: ((lon + 540) % 360) - 180})
      });
      if (res.status === 401) { window.location = '/login'; return; }
      const data = await res.json();
      if (!res.ok) { $('status').textContent = data.error || 'Something went wrong.'; return; }
      $('status').textContent = 'Analysis for the selected point:';
      render(data);
    } catch (err) {
      $('status').textContent = 'Network error. Please try again.';
    }
  });
})();
