/* Ruang kerja Recens — satu alur kerja untuk seluruh jenis karya tulis ilmiah. */

const S = {
  catalog: null, projects: [], project: null, view: 'buat_proyek',
  manuscript: null, sectionId: null, datasets: [], columns: [], checks: null,
};

const $ = (sel, root = document) => root.querySelector(sel);
const view = () => $('#view');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (n, d = 0) => (n === null || n === undefined) ? '–'
  : Number(n).toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });

function toast(message, isError = false) {
  const el = $('#toast');
  el.textContent = message;
  el.className = `show${isError ? ' err' : ''}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = ''; }, isError ? 7000 : 3200);
}

async function api(path, options = {}) {
  const config = { headers: {}, ...options };
  if (config.body && !(config.body instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(`/api${path}`, config);
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? payload;
    // Penolakan batas produk dikembalikan lengkap dengan jalan keluarnya.
    if (detail && typeof detail === 'object' && detail.error === 'batas_produk') {
      throw Object.assign(new Error(detail.message), { verdict: detail });
    }
    throw new Error(typeof detail === 'string' ? detail : (detail.message || 'Permintaan gagal.'));
  }
  return payload;
}

async function run(fn, busyEl) {
  const original = busyEl?.innerHTML;
  if (busyEl) { busyEl.disabled = true; busyEl.innerHTML = '<span class="spin"></span>'; }
  try {
    return await fn();
  } catch (error) {
    if (error.verdict) showVerdict(error.verdict); else toast(error.message, true);
    return null;
  } finally {
    if (busyEl) { busyEl.disabled = false; busyEl.innerHTML = original; }
  }
}

function showVerdict(v) {
  toast(v.message, true);
  const box = document.createElement('div');
  box.className = 'note-box danger';
  box.style.cssText = 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);max-width:640px;z-index:60';
  box.innerHTML = `<strong>Batas produk: ${esc(v.rule)}</strong>${esc(v.message)}
    <div style="margin-top:8px"><strong>Yang bisa dikerjakan</strong>${esc(v.alternative)}</div>
    <button class="btn ghost small" style="margin-top:8px">Tutup</button>`;
  box.querySelector('button').onclick = () => box.remove();
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 20000);
}

/* ---------------------------------------------------------------- navigasi */

const STEP_VIEWS = ['buat_proyek', 'muat_aturan', 'kumpulkan_referensi', 'susun_outline',
  'menulis', 'olah_data', 'periksa_naskah', 'ekspor_revisi'];

function renderNav() {
  const steps = S.project?.steps ?? S.catalog.steps.map((s) => ({ ...s, active: true }));
  $('#step-nav').innerHTML = steps.map((s) => `
    <button class="step ${S.view === s.key ? 'active' : ''} ${s.active === false ? 'inactive' : ''}"
            data-view="${s.key}">
      <span class="num">${s.number}</span>
      <span><span class="t">${esc(s.title)}</span>
      ${s.note ? `<br><span class="note">${esc(s.note)}</span>` : ''}
      ${s.active === false ? '<br><span class="note">opsional untuk karya ini</span>' : ''}</span>
    </button>`).join('');
  document.querySelectorAll('.step').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === S.view);
    btn.onclick = () => { S.view = btn.dataset.view; render(); };
  });
}

async function refreshProject(id) {
  S.project = await api(`/projects/${id}`);
  S.manuscript = await api(`/projects/${id}/manuscript`);
  if (!S.sectionId) S.sectionId = firstWritable(S.manuscript.sections)?.id ?? null;
}

function firstWritable(sections) {
  for (const s of sections) {
    if (!s.children.length) return s;
    const found = firstWritable(s.children);
    if (found) return found;
  }
  return sections[0] ?? null;
}

function flatten(sections, out = []) {
  for (const s of sections) { out.push(s); flatten(s.children, out); }
  return out;
}

async function render() {
  renderNav();
  const views = {
    buat_proyek: viewProject, muat_aturan: viewRules, kumpulkan_referensi: viewReferences,
    susun_outline: viewOutline, menulis: viewEditor, olah_data: viewData,
    periksa_naskah: viewChecks, ekspor_revisi: viewExport,
    dashboard: viewDashboard, limits: viewLimits,
  };
  if (!S.project && STEP_VIEWS.indexOf(S.view) > 0) {
    view().innerHTML = `<div class="panel"><div class="empty">
      Pilih atau buat proyek lebih dahulu di langkah 1.</div></div>`;
    return;
  }
  await views[S.view]();
}

/* ------------------------------------------------- 1. Buat proyek */

async function viewProject() {
  const c = S.catalog;
  const p = S.project;
  view().innerHTML = `
    <div class="panel">
      <h2>Buat proyek</h2>
      <p class="sub">Pilihan jenis karya menentukan struktur bawaan, batas panjang, dan
        langkah mana yang dipakai.</p>

      <div class="card">
        <h3>Proyek baru</h3>
        <div class="row">
          <div class="field grow"><label>Judul karya</label>
            <input type="text" id="np-name" placeholder="Pengaruh … terhadap …"></div>
          <div class="field"><label>Jenis karya</label>
            <select id="np-work">${c.work_types.map((w) =>
              `<option value="${w.key}">${esc(w.label)}</option>`).join('')}</select></div>
          <div class="field"><label>Jenis penelitian</label>
            <select id="np-research">${c.research_types.map((r) =>
              `<option value="${r.key}">${esc(r.label)}</option>`).join('')}</select></div>
          <div class="field"><label>Bidang ilmu</label>
            <input type="text" id="np-field" placeholder="Manajemen" style="width:140px"></div>
          <div class="field"><label>Target sidang</label>
            <input type="date" id="np-deadline"></div>
          <button class="btn" id="np-create">Buat proyek</button>
        </div>
        <div id="np-preview" style="margin-top:12px"></div>
      </div>

      ${p ? projectDetailCard(p) : ''}

      <div class="card">
        <h3>Proyek tersimpan</h3>
        <div class="list">${S.projects.length ? S.projects.map((x) => `
          <div class="item" style="display:flex;justify-content:space-between;gap:10px">
            <div><strong>${esc(x.name)}</strong>
              <div class="meta">${esc(x.work_type_label)} · ${num(x.word_count)} kata
                dari ${num(x.target_words)}</div></div>
            <button class="btn ghost small" data-open="${x.id}">Buka</button>
          </div>`).join('') : '<div class="empty">Belum ada proyek.</div>'}
        </div>
      </div>
    </div>`;

  const preview = () => {
    const w = c.work_types.find((x) => x.key === $('#np-work').value);
    $('#np-preview').innerHTML = `<div class="note-box"><strong>${esc(w.label)}</strong>
      ${esc(w.ciri_khas)}<br>
      <span class="meta">Struktur bawaan: ${w.structure.map(esc).join(' · ')}</span><br>
      <span class="meta">Target ${num(w.default_target_words)} kata
      ${w.hard_word_limit ? `· batas keras ${num(w.hard_word_limit)} kata` : ''}
      · gaya sitasi ${w.citation_style.toUpperCase()}
      · ekspor ${w.export_formats.join(', ')}</span></div>`;
  };
  $('#np-work').onchange = preview; preview();

  $('#np-create').onclick = (e) => run(async () => {
    const name = $('#np-name').value.trim();
    if (!name) return toast('Judul karya belum diisi.', true);
    const created = await api('/projects', { method: 'POST', body: {
      name, work_type: $('#np-work').value, research_type: $('#np-research').value,
      field_of_study: $('#np-field').value || null,
      deadline: $('#np-deadline').value || null } });
    S.projects = await api('/projects');
    S.sectionId = null;
    await refreshProject(created.id);
    syncPicker();
    S.view = 'muat_aturan';
    toast(`Proyek dibuat dengan ${created.counts ? '' : ''}kerangka bawaan.`);
    render();
  }, e.currentTarget);

  view().querySelectorAll('[data-open]').forEach((b) => {
    b.onclick = () => run(async () => {
      S.sectionId = null;
      await refreshProject(Number(b.dataset.open));
      syncPicker(); render();
    });
  });
}

function projectDetailCard(p) {
  const d = p.work_type_detail;
  return `<div class="card">
    <h3>Proyek aktif</h3>
    <div class="metrics" style="margin-bottom:12px">
      <div class="metric"><div class="v">${num(p.word_count)}</div><div class="k">kata tertulis</div></div>
      <div class="metric"><div class="v">${num(p.target_words)}</div><div class="k">target kata</div></div>
      <div class="metric"><div class="v">${p.counts.references}</div><div class="k">referensi (${p.counts.references_verified} terverifikasi)</div></div>
      <div class="metric"><div class="v">${p.counts.analyses}</div><div class="k">analisis tersimpan</div></div>
      <div class="metric"><div class="v">${p.counts.revisions_open}</div><div class="k">revisi terbuka</div></div>
    </div>
    <table><tbody>
      <tr><th style="width:180px">Jenis karya</th><td>${esc(p.work_type_label)} — ${esc(d.ciri_khas)}</td></tr>
      <tr><th>Jenis penelitian</th><td>${esc(p.research_type_label)}<br>
        <span class="meta">${esc(p.research_needs)}</span></td></tr>
      <tr><th>Sumber aturan</th><td>${esc(p.treatment.sumber_aturan)}</td></tr>
      <tr><th>Struktur</th><td>${esc(p.treatment.struktur)}</td></tr>
      <tr><th>Batas panjang</th><td>${esc(p.treatment.batas_panjang)}</td></tr>
      <tr><th>Gaya sitasi</th><td>${esc(p.treatment.gaya_sitasi)}</td></tr>
      <tr><th>Siklus revisi</th><td>${esc(p.treatment.siklus_revisi)}</td></tr>
      <tr><th>Keluaran</th><td>${esc(p.treatment.keluaran)}</td></tr>
      <tr><th>Fitur paling berperan</th><td>${d.fitur_utama.map((f) =>
        `<span class="tag">${esc(f)}</span>`).join(' ')}</td></tr>
    </tbody></table></div>`;
}

/* ------------------------------------------------- 2. Muat aturan */

async function viewRules() {
  const data = await api(`/projects/${S.project.id}/guidelines`);
  const r = data.active;
  const m = r.margins;
  const ev = (k) => r.evidence?.[k] ? `<div class="meta" style="font-style:italic">“${esc(r.evidence[k])}”</div>` : '';

  view().innerHTML = `
    <div class="panel">
      <h2>Muat aturan penulisan</h2>
      <p class="sub">Pedoman dibaca menjadi aturan yang mengikat seluruh keluaran: struktur,
        gaya sitasi, margin, huruf, spasi, penomoran, dan batas panjang.</p>

      <div class="card">
        <h3>Unggah atau tempel pedoman</h3>
        <p class="hint">Pedoman fakultas, instruksi dosen, ketentuan panitia lomba, atau
          pedoman penulis jurnal tujuan.</p>
        <div class="row">
          <div class="field"><label>Berkas PDF/DOCX</label><input type="file" id="gl-file" accept=".pdf,.docx,.txt"></div>
          <div class="field"><label>Nama</label><input type="text" id="gl-name" value="Pedoman penulisan"></div>
          <div class="field"><label>Jenis</label><select id="gl-kind">
            <option value="fakultas">Pedoman fakultas</option><option value="dosen">Instruksi dosen</option>
            <option value="panitia">Ketentuan panitia</option><option value="jurnal">Pedoman jurnal</option>
          </select></div>
          <button class="btn" id="gl-upload">Baca berkas</button>
        </div>
        <div class="field" style="margin-top:10px"><label>Atau tempel teks pedoman</label>
          <textarea id="gl-text" placeholder="Naskah diketik pada kertas A4 dengan huruf Times New Roman ukuran 12 pt, jarak 2 spasi, margin atas 4 cm…"></textarea></div>
        <button class="btn ghost" id="gl-parse" style="margin-top:8px">Baca teks</button>
      </div>

      <div class="card">
        <h3>Aturan yang berlaku sekarang — ${esc(r.name)}</h3>
        ${r.assumed?.length ? `<div class="note-box warn" style="margin-bottom:10px">
          <strong>${r.assumed.length} aturan memakai nilai bawaan</strong>
          Tidak ditemukan di pedoman: ${r.assumed.map(esc).join(', ')}. Periksa dan perbaiki
          di bawah sebelum naskah dirakit.</div>` : ''}
        <div class="scroll-x"><table><tbody>
          <tr><th style="width:190px">Ukuran kertas</th><td>${esc(r.page_size)}</td></tr>
          <tr><th>Huruf</th><td>${esc(r.font_family)}, ${r.font_size_pt} pt ${ev('font_family')}${ev('font_size_pt')}</td></tr>
          <tr><th>Jarak baris</th><td>${r.line_spacing} spasi ${ev('line_spacing')}</td></tr>
          <tr><th>Margin (atas/kanan/bawah/kiri)</th>
            <td>${m.top_cm} / ${m.right_cm} / ${m.bottom_cm} / ${m.left_cm} cm</td></tr>
          <tr><th>Gaya sitasi</th><td>${esc(r.citation_style.toUpperCase())}
            ${r.citation_options?.et_al_term ? `<span class="tag">${esc(r.citation_options.et_al_term)}</span>` : ''}
            ${ev('citation_style')}</td></tr>
          <tr><th>Penomoran halaman</th><td>Bagian awal ${esc(r.front_matter_numbering)},
            bagian isi ${esc(r.body_numbering)}</td></tr>
          <tr><th>Caption</th><td>Judul tabel di ${posisi(r.table_caption_position)},
            judul gambar di ${posisi(r.figure_caption_position)}, penomoran ${esc(r.caption_numbering)}</td></tr>
          <tr><th>Batas panjang</th><td>
            ${r.max_words ? num(r.max_words) + ' kata' : 'tidak ditetapkan'} ·
            ${r.max_pages ? num(r.max_pages) + ' halaman' : 'halaman tidak dibatasi'} ·
            abstrak ${r.abstract_max_words ? num(r.abstract_max_words) + ' kata' : 'tidak dibatasi'}
            ${ev('max_pages')}${ev('abstract_max_words')}</td></tr>
          <tr><th>Bab wajib</th><td>${r.required_sections?.length
            ? r.required_sections.map((s) => `<span class="tag">${esc(s)}</span>`).join(' ')
            : '<span class="meta">tidak terbaca dari pedoman</span>'}</td></tr>
        </tbody></table></div>
      </div>

      ${data.history.length > 1 ? `<div class="card"><h3>Riwayat pedoman</h3>
        <div class="list">${data.history.map((h) => `<div class="item">
          ${esc(h.name)} <span class="tag">${esc(h.kind)}</span>
          ${h.active ? '<span class="tag ok">aktif</span>' : ''}
          <div class="meta">${esc(h.created_at)}</div></div>`).join('')}</div></div>` : ''}
    </div>`;

  $('#gl-upload').onclick = (e) => run(async () => {
    const file = $('#gl-file').files[0];
    if (!file) return toast('Pilih berkas pedoman lebih dahulu.', true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', $('#gl-name').value);
    fd.append('kind', $('#gl-kind').value);
    const res = await api(`/projects/${S.project.id}/guidelines/upload`, { method: 'POST', body: fd });
    toast(`Pedoman terbaca dari ${res.pages_read} halaman.`);
    render();
  }, e.currentTarget);

  $('#gl-parse').onclick = (e) => run(async () => {
    const text = $('#gl-text').value.trim();
    if (!text) return toast('Teks pedoman masih kosong.', true);
    await api(`/projects/${S.project.id}/guidelines/text`, { method: 'POST', body: {
      text, name: $('#gl-name').value, kind: $('#gl-kind').value } });
    toast('Aturan diperbarui.');
    render();
  }, e.currentTarget);
}

/* ------------------------------------------------- 3. Referensi */

async function viewReferences() {
  const lib = await api(`/projects/${S.project.id}/references`);
  view().innerHTML = `
    <div class="panel">
      <h2>Kumpulkan referensi</h2>
      <p class="sub">Metadata sitasi hanya berasal dari basis data ilmiah resmi. Referensi
        unggahan sendiri ditandai jelas sampai berhasil ditelusuri.</p>

      <div class="tabs">
        <button class="tab active" data-rt="cari">Pencarian literatur</button>
        <button class="tab" data-rt="pustaka">Pustaka proyek (${lib.count})</button>
        <button class="tab" data-rt="tanya">Tanya jurnal</button>
        <button class="tab" data-rt="sintesis">Matriks sintesis</button>
      </div>
      <div id="ref-body"></div>
    </div>`;

  const tabs = {
    cari: () => `<div class="card"><h3>Penelusuran serentak</h3>
        <p class="hint">Crossref, OpenAlex, Semantic Scholar, dan Garuda/SINTA dicari sekaligus.</p>
        <div class="row"><div class="field grow"><label>Kata kunci</label>
          <input type="text" id="rs-q" placeholder="motivasi kerja kinerja karyawan"></div>
          <button class="btn" id="rs-go">Cari</button></div>
        <div class="row" style="margin-top:10px"><div class="field grow"><label>Atau tambah lewat DOI</label>
          <input type="text" id="rs-doi" placeholder="10.1016/j.jbusres.2020.01.001"></div>
          <button class="btn ghost" id="rs-doi-go">Tarik metadata</button></div>
        <div class="row" style="margin-top:10px"><div class="field grow"><label>Atau unggah PDF sendiri</label>
          <input type="file" id="rs-pdf" accept=".pdf"></div>
          <button class="btn ghost" id="rs-pdf-go">Unggah & indeks</button></div>
        <div id="rs-results" style="margin-top:12px"></div></div>`,
    pustaka: () => `<div class="card"><h3>Pustaka proyek</h3>
        <div class="list">${lib.references.length ? lib.references.map((r) => {
          const e = r.csl_json;
          return `<div class="item"><div style="display:flex;justify-content:space-between;gap:10px">
            <div><span class="cite-chip">${esc(r.citekey)}</span> <strong>${esc(titleOf(e))}</strong>
              <div class="meta">${esc(authorsOf(e))} (${esc(yearOf(e))}) · ${esc(containerOf(e))}
                ${e.DOI ? `· doi:${esc(e.DOI)}` : ''}</div>
              <div style="margin-top:3px">
                ${r.verified ? `<span class="tag ok">terverifikasi · ${esc(r.source_db)}</span>`
                  : '<span class="tag warn">belum terverifikasi</span>'}</div></div>
            <div style="display:flex;gap:5px;align-items:flex-start">
              ${!r.verified ? `<button class="btn ghost small" data-verify="${r.id}">Telusuri</button>` : ''}
              <button class="btn ghost small" data-del="${r.id}">Hapus</button></div>
          </div></div>`; }).join('')
          : '<div class="empty">Pustaka masih kosong.</div>'}</div></div>`,
    tanya: () => `<div class="card"><h3>Tanya jurnal</h3>
        <p class="hint">Jawaban disertai penunjuk halaman sumber. Hanya berlaku untuk PDF yang
          sudah diunggah dan diindeks.</p>
        <div class="row"><div class="field grow"><label>Pertanyaan</label>
          <input type="text" id="ask-q" placeholder="Apa metode dan ukuran sampel penelitian ini?"></div>
          <button class="btn" id="ask-go">Tanya</button></div>
        <div id="ask-out" style="margin-top:12px"></div></div>`,
    sintesis: () => `<div class="card"><h3>Matriks sintesis</h3>
        <p class="hint">Mengubah tumpukan bacaan menjadi tabel perbandingan: penulis, tahun,
          teori, metode, temuan, dan celah penelitian.</p>
        <button class="btn" id="syn-go">Susun matriks</button>
        <div id="syn-out" style="margin-top:12px"></div></div>`,
  };

  const showTab = (key) => {
    $('#ref-body').innerHTML = tabs[key]();
    view().querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.rt === key));
    bindRefTab(key, lib);
  };
  view().querySelectorAll('.tab').forEach((t) => { t.onclick = () => showTab(t.dataset.rt); });
  showTab('cari');
}

const posisi = (v) => ({ above: 'atas', below: 'bawah' }[v] ?? esc(v));
const titleOf = (e) => Array.isArray(e.title) ? e.title[0] : (e.title || '(tanpa judul)');
const containerOf = (e) => Array.isArray(e['container-title']) ? e['container-title'][0] : (e['container-title'] || '');
const yearOf = (e) => e.issued?.['date-parts']?.[0]?.[0] || 't.t.';
const authorsOf = (e) => (e.author || []).map((a) => a.family || a.literal || '').filter(Boolean).join(', ') || '—';

function bindRefTab(key, lib) {
  const pid = S.project.id;
  if (key === 'cari') {
    $('#rs-go').onclick = (ev) => run(async () => {
      const q = $('#rs-q').value.trim();
      if (!q) return toast('Kata kunci masih kosong.', true);
      const res = await api(`/references/search?q=${encodeURIComponent(q)}&rows=10&project_id=${pid}`);
      const failed = Object.entries(res.sources_failed || {});
      $('#rs-results').innerHTML = `
        ${failed.length ? `<div class="note-box warn" style="margin-bottom:10px">
          <strong>Sebagian sumber tidak terjangkau</strong>
          ${failed.map(([k, v]) => `${esc(k)}: ${esc(v)}`).join('<br>')}</div>` : ''}
        <div class="meta" style="margin-bottom:6px">${res.count} hasil dari
          ${(res.sources_searched || []).join(', ') || 'tidak ada sumber'}.</div>
        <div class="list">${res.results.map((r, i) => `<div class="item">
          <strong>${esc(titleOf(r.entry))}</strong>
          <div class="meta">${esc(authorsOf(r.entry))} (${esc(yearOf(r.entry))}) ·
            ${esc(containerOf(r.entry))} · <span class="tag ok">${esc(r.source_db)}</span></div>
          <button class="btn ghost small" style="margin-top:5px" data-add="${i}">Tambah ke pustaka</button>
        </div>`).join('')}</div>`;
      $('#rs-results').querySelectorAll('[data-add]').forEach((b) => {
        b.onclick = () => run(async () => {
          const r = res.results[Number(b.dataset.add)];
          await api(`/projects/${pid}/references`, { method: 'POST', body: {
            entry: r.entry, source_db: r.source_db, external_id: r.external_id, abstract: r.abstract } });
          toast('Referensi masuk pustaka proyek.');
        }, b);
      });
    }, ev.currentTarget);

    $('#rs-doi-go').onclick = (ev) => run(async () => {
      const doi = $('#rs-doi').value.trim();
      if (!doi) return toast('DOI masih kosong.', true);
      const r = await api(`/projects/${pid}/references/doi`, { method: 'POST', body: { doi } });
      toast(`Ditambahkan: ${r.citekey}`); render();
    }, ev.currentTarget);

    $('#rs-pdf-go').onclick = (ev) => run(async () => {
      const file = $('#rs-pdf').files[0];
      if (!file) return toast('Pilih berkas PDF lebih dahulu.', true);
      const fd = new FormData(); fd.append('file', file);
      const r = await api(`/projects/${pid}/references/upload`, { method: 'POST', body: fd });
      toast(`${r.pages} halaman terindeks jadi ${r.chunks} potongan. ${r.note}`);
      render();
    }, ev.currentTarget);
  }

  if (key === 'pustaka') {
    view().querySelectorAll('[data-verify]').forEach((b) => b.onclick = () => run(async () => {
      const r = await api(`/references/${b.dataset.verify}/verify`, { method: 'POST' });
      toast(r.verified ? 'Terverifikasi ke basis data resmi.' : r.note); render();
    }, b));
    view().querySelectorAll('[data-del]').forEach((b) => b.onclick = () => run(async () => {
      await api(`/references/${b.dataset.del}`, { method: 'DELETE' }); render();
    }, b));
  }

  if (key === 'tanya') {
    $('#ask-go').onclick = (ev) => run(async () => {
      const question = $('#ask-q').value.trim();
      if (!question) return toast('Pertanyaan masih kosong.', true);
      const res = await api(`/projects/${pid}/ask`, { method: 'POST', body: { question } });
      const sources = res.meta.sources || [];
      $('#ask-out').innerHTML = `
        ${res.text ? `<div class="note-box ok" style="margin-bottom:10px">${esc(res.text)}</div>` : ''}
        ${res.meta.note ? `<div class="note-box" style="margin-bottom:10px">${esc(res.meta.note)}</div>` : ''}
        <div class="list">${sources.map((s) => `<div class="item">
          <span class="cite-chip">${esc(s.citekey)}</span>
          <span class="tag">hlm. ${s.page ?? '?'}</span>
          <div style="margin-top:5px">${esc(s.text.slice(0, 420))}…</div></div>`).join('')}</div>`;
    }, ev.currentTarget);
  }

  if (key === 'sintesis') {
    $('#syn-go').onclick = (ev) => run(async () => {
      const res = await api(`/projects/${pid}/synthesis`, { method: 'POST', body: {} });
      $('#syn-out').innerHTML = res.rows.length ? `<div class="scroll-x"><table>
        <thead><tr>${res.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${res.rows.map((r) => `<tr>${res.columns.map((c) =>
          `<td>${esc(String(r[c] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
      </table></div>` : '<div class="empty">Pustaka masih kosong.</div>';
    }, ev.currentTarget);
  }
}

/* ------------------------------------------------- 4. Outline */

async function viewOutline() {
  const data = await api(`/projects/${S.project.id}/outline`);
  view().innerHTML = `
    <div class="panel">
      <h2>Susun outline</h2>
      <p class="sub">Kerangka dibangun mengikuti struktur yang berlaku pada jenis karya ini,
        lengkap dengan target jumlah kata tiap bagian.</p>
      <div class="card">
        <h3>Kerangka — ${num(data.word_count)} dari ${num(data.target_words)} kata</h3>
        <div class="row" style="margin-bottom:12px">
          <div class="field"><label>Target kata</label>
            <input type="number" id="ol-target" value="${data.target_words}" style="width:120px"></div>
          <button class="btn ghost" id="ol-regen">Bangun ulang kerangka</button>
          <span class="meta" style="align-self:center">Membangun ulang menghapus isi yang sudah ditulis.</span>
        </div>
        <div class="scroll-x"><table>
          <thead><tr><th>Bagian</th><th style="width:90px">Kata</th><th style="width:90px">Target</th>
            <th style="width:130px">Kemajuan</th><th style="width:90px">Status</th></tr></thead>
          <tbody>${data.sections.map((s) => `<tr>
            <td style="padding-left:${(s.level - 1) * 18 + 9}px">
              ${s.level === 1 ? '<strong>' : ''}${esc(s.number)} ${esc(s.title)}${s.level === 1 ? '</strong>' : ''}
              ${s.role ? `<span class="tag">${esc(s.role)}</span>` : ''}</td>
            <td>${num(s.word_count)}</td><td>${num(s.target_words)}</td>
            <td><div class="bar"><i style="width:${Math.min(100, s.progress * 100)}%"></i></div></td>
            <td><span class="tag ${s.status === 'selesai' ? 'ok' : ''}">${esc(s.status)}</span></td>
          </tr>`).join('')}</tbody></table></div>
      </div>
    </div>`;

  $('#ol-regen').onclick = (e) => run(async () => {
    if (!confirm('Bangun ulang kerangka? Seluruh isi bagian akan terhapus.')) return;
    await api(`/projects/${S.project.id}/versions`, { method: 'POST', body: { label: 'Sebelum bangun ulang kerangka' } });
    await api(`/projects/${S.project.id}/outline/generate`, { method: 'POST', body: {
      reset: true, target_words: Number($('#ol-target').value) } });
    S.sectionId = null;
    await refreshProject(S.project.id);
    toast('Kerangka dibangun ulang. Versi sebelumnya tersimpan.');
    render();
  }, e.currentTarget);
}

/* ------------------------------------------------- 5. Editor */

async function viewEditor() {
  const flat = flatten(S.manuscript.sections);
  const section = flat.find((s) => s.id === S.sectionId) ?? flat[0];
  S.sectionId = section?.id ?? null;
  const citekeys = S.manuscript.citekeys;

  view().innerHTML = `
    <div class="panel" style="max-width:1200px">
      <h2>Menulis di editor</h2>
      <p class="sub">Editor mengenali bab, sub-bab, kutipan, tabel, gambar, dan caption sebagai
        bagian terpisah — dasar bagi format otomatis dan pemeriksaan menyeluruh.</p>
      <div class="editor-grid">
        <div class="card outline-tree">
          <h3>Kerangka</h3>
          ${flat.map((s) => `<button class="tree-item lvl${s.level} ${s.id === S.sectionId ? 'active' : ''}"
            data-sec="${s.id}"><span class="wc">${num(s.word_count)}</span>
            ${esc(s.number)} ${esc(s.title)}</button>`).join('')}
        </div>
        <div>
          <div class="card">
            <h3>${esc(section?.number ?? '')} ${esc(section?.title ?? 'Tidak ada bagian')}</h3>
            <div class="row" style="margin-bottom:10px">
              <button class="btn ghost small" data-add="paragraph">+ Paragraf</button>
              <button class="btn ghost small" data-add="quote">+ Kutipan</button>
              <button class="btn ghost small" data-add="list">+ Daftar</button>
              <span class="meta" style="align-self:center">
                ${num(section?.word_count ?? 0)} / ${num(section?.target_words ?? 0)} kata target</span>
            </div>
            <div id="blocks">${(section?.blocks ?? []).map(blockHtml).join('')
              || '<div class="empty">Bagian ini masih kosong. Tambahkan paragraf untuk mulai menulis.</div>'}</div>
          </div>
          <div class="card">
            <h3>Bantuan menulis</h3>
            <div class="row">
              <div class="field"><label>Sisipkan sitasi</label>
                <select id="ed-cite" style="width:190px">
                  <option value="">— pilih dari pustaka —</option></select></div>
              <button class="btn ghost small" id="ed-cite-go">Salin penanda</button>
            </div>
            <div class="meta" style="margin-top:6px">Sitasi dalam teks memakai penanda
              <span class="cite-chip">[[cite:citekey]]</span> sehingga selalu sinkron dengan
              daftar pustaka apa pun gaya sitasinya.
              ${citekeys.length ? `Dipakai di naskah: ${citekeys.map((k) =>
                `<span class="cite-chip">${esc(k)}</span>`).join(' ')}` : ''}</div>
            <div id="ed-out" style="margin-top:10px"></div>
          </div>
        </div>
      </div>
    </div>`;

  view().querySelectorAll('[data-sec]').forEach((b) => b.onclick = () => {
    S.sectionId = Number(b.dataset.sec); render();
  });
  view().querySelectorAll('[data-add]').forEach((b) => b.onclick = () => run(async () => {
    await api(`/sections/${S.sectionId}/blocks`, { method: 'POST', body: { kind: b.dataset.add, content: '' } });
    await refreshProject(S.project.id); render();
  }, b));

  bindBlocks();
  api(`/projects/${S.project.id}/references`).then((lib) => {
    const sel = $('#ed-cite');
    if (!sel) return;
    sel.innerHTML += lib.references.map((r) =>
      `<option value="${esc(r.citekey)}">${esc(r.citekey)} — ${esc(titleOf(r.csl_json).slice(0, 46))}</option>`).join('');
  });
  $('#ed-cite-go').onclick = () => {
    const key = $('#ed-cite').value;
    if (!key) return toast('Pilih referensi lebih dahulu.', true);
    const marker = `[[cite:${key}]]`;
    navigator.clipboard?.writeText(marker);
    $('#ed-out').innerHTML = `<div class="note-box ok">Penanda disalin: <span class="cite-chip">${esc(marker)}</span>
      — tempelkan di posisi kutipan dalam paragraf.</div>`;
  };
}

function blockHtml(b) {
  const kindLabel = { paragraph: 'Paragraf', quote: 'Kutipan langsung', list: 'Daftar',
    table: 'Tabel', figure: 'Gambar', equation: 'Persamaan' }[b.kind] || b.kind;
  if (b.kind === 'table') {
    const m = b.meta || {};
    return `<div class="block"><div class="block-head"><strong>${kindLabel}</strong>
      <span>${esc(m.caption || '')}</span><span style="flex:1"></span>
      <button class="btn ghost small" data-delblock="${b.id}">Hapus</button></div>
      <div class="scroll-x" style="padding:9px">
      <table><thead><tr>${(m.columns || []).map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
      <tbody>${(m.rows || []).slice(0, 12).map((r) => `<tr>${r.map((v) =>
        `<td>${esc(v ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>
      ${m.note ? `<div class="meta" style="margin-top:6px">${esc(m.note)}</div>` : ''}</div></div>`;
  }
  return `<div class="block">
    <div class="block-head"><strong>${kindLabel}</strong>
      <span>${num(b.word_count)} kata</span><span style="flex:1"></span>
      <button class="btn ghost small" data-continue="${b.id}">Lanjutkan kalimat</button>
      <button class="btn ghost small" data-lang="${b.id}">Perbaiki bahasa</button>
      <button class="btn ghost small" data-para="${b.id}">Parafrase</button>
      <button class="btn ghost small" data-delblock="${b.id}">Hapus</button></div>
    <textarea data-block="${b.id}">${esc(b.content)}</textarea></div>`;
}

function bindBlocks() {
  const save = (id, content) => api(`/blocks/${id}`, { method: 'PATCH', body: { content } });

  view().querySelectorAll('[data-block]').forEach((ta) => {
    ta.onblur = () => run(async () => {
      await save(Number(ta.dataset.block), ta.value);
      await refreshProject(S.project.id);
      renderNav();
    });
  });
  view().querySelectorAll('[data-delblock]').forEach((b) => b.onclick = () => run(async () => {
    await api(`/blocks/${b.dataset.delblock}`, { method: 'DELETE' });
    await refreshProject(S.project.id); render();
  }, b));

  view().querySelectorAll('[data-continue]').forEach((b) => b.onclick = () => run(async () => {
    const ta = view().querySelector(`[data-block="${b.dataset.continue}"]`);
    const res = await api(`/projects/${S.project.id}/continue`, { method: 'POST', body: {
      context: ta.value, section_id: S.sectionId } });
    if (!res.text) {
      $('#ed-out').innerHTML = `<div class="note-box warn">${esc(res.meta.hint || res.meta.unavailable || 'Model belum tersedia.')}</div>`;
      return;
    }
    ta.value = `${ta.value.trimEnd()} ${res.text}`;
    await save(Number(b.dataset.continue), ta.value);
    reportVerdict(res);
    await refreshProject(S.project.id);
  }, b));

  view().querySelectorAll('[data-lang]').forEach((b) => b.onclick = () => run(async () => {
    const ta = view().querySelector(`[data-block="${b.dataset.lang}"]`);
    const res = await api(`/projects/${S.project.id}/language`, { method: 'POST', body: { text: ta.value } });
    ta.value = res.text;
    await save(Number(b.dataset.lang), res.text);
    const findings = res.meta.findings || [];
    $('#ed-out').innerHTML = `<div class="note-box ${findings.length ? 'warn' : 'ok'}">
      <strong>${findings.length} temuan kaidah bahasa</strong>
      ${res.meta.note ? esc(res.meta.note) : ''}</div>
      ${findings.slice(0, 8).map((f) => `<div class="finding ${f.severity}">
        <strong>${esc(f.rule)}</strong> — ${esc(f.message)}
        <span class="ex">${esc(f.excerpt)}</span>
        <span class="sug">→ ${esc(f.suggestion)}</span></div>`).join('')}`;
    await refreshProject(S.project.id);
  }, b));

  view().querySelectorAll('[data-para]').forEach((b) => b.onclick = () => run(async () => {
    const ta = view().querySelector(`[data-block="${b.dataset.para}"]`);
    const res = await api(`/projects/${S.project.id}/paraphrase`, { method: 'POST', body: { text: ta.value } });
    $('#ed-out').innerHTML = `<div class="note-box"><strong>Usulan parafrase</strong>${esc(res.text)}
      ${res.meta.explanation ? `<div style="margin-top:8px"><strong>Alasan perubahan</strong>${esc(res.meta.explanation)}</div>` : ''}
      ${res.meta.reminder ? `<div class="meta" style="margin-top:6px">${esc(res.meta.reminder)}</div>` : ''}
      <button class="btn small" id="para-apply" style="margin-top:8px">Pakai usulan ini</button></div>`;
    $('#para-apply').onclick = () => run(async () => {
      ta.value = res.text;
      await save(Number(b.dataset.para), res.text);
      await refreshProject(S.project.id); render();
    });
  }, b));
}

function reportVerdict(res) {
  const adjustments = res.verdict?.adjustments ?? [];
  if (adjustments.length) {
    $('#ed-out').innerHTML = `<div class="note-box warn"><strong>Penyesuaian otomatis</strong>
      ${adjustments.map(esc).join('<br>')}</div>`;
  }
}

/* ------------------------------------------------- 6. Olah data */

async function viewData() {
  const [methods, datasets, analyses, options] = await Promise.all([
    api('/analysis/methods'), api(`/projects/${S.project.id}/datasets`),
    api(`/projects/${S.project.id}/analyses`), api('/methodology/options'),
  ]);
  S.datasets = datasets;

  view().innerHTML = `
    <div class="panel" style="max-width:1150px">
      <h2>Olah data penelitian</h2>
      <p class="sub">${esc(methods.boundary)}</p>

      <div class="tabs">
        <button class="tab active" data-dt="uji">Menjalankan uji</button>
        <button class="tab" data-dt="pemandu">Pemandu metodologi</button>
        <button class="tab" data-dt="kualitatif">Analisis kualitatif</button>
        <button class="tab" data-dt="jejak">Jejak analisis (${analyses.length})</button>
      </div>
      <div id="data-body"></div>
    </div>`;

  const bodies = {
    uji: () => `
      <div class="card"><h3>Unggah data</h3>
        <p class="hint">Diterima: ${methods.accepted_files.join(', ')} — SPSS, Excel, CSV,
          dan transkrip wawancara.</p>
        <div class="row"><div class="field grow"><input type="file" id="ds-file"></div>
          <button class="btn" id="ds-up">Unggah</button></div>
        <div class="list" style="margin-top:10px">${datasets.map((d) => `<div class="item">
          <strong>${esc(d.filename)}</strong> <span class="tag">${esc(d.kind)}</span>
          <div class="meta">${d.meta_json.n_rows} baris ·
            ${(d.meta_json.columns || []).length} kolom</div>
          ${(d.meta_json.notes || []).map((n) => `<div class="meta">• ${esc(n)}</div>`).join('')}
        </div>`).join('') || '<div class="empty">Belum ada data.</div>'}</div></div>

      <div class="card"><h3>Jalankan uji</h3>
        <div class="row">
          <div class="field"><label>Data</label><select id="an-ds">${datasets.map((d) =>
            `<option value="${d.id}">${esc(d.filename)}</option>`).join('')}</select></div>
          <div class="field"><label>Uji</label><select id="an-method">${methods.methods.map((m) =>
            `<option value="${m.key}">${esc(m.label)}</option>`).join('')}</select></div>
        </div>
        <div id="an-params" class="row" style="margin-top:10px"></div>
        <button class="btn" id="an-run" style="margin-top:10px">Jalankan</button>
        <div id="an-out" style="margin-top:12px"></div></div>`,

    pemandu: () => `<div class="card"><h3>Pemandu metodologi</h3>
        <p class="hint">Pemilihan uji mengikuti pertanyaan penelitian, skala data, jumlah
          kelompok, dan sebaran data.</p>
        <div class="row">
          <div class="field"><label>Tujuan</label><select id="mg-purpose">${options.purposes.map((p) =>
            `<option value="${p.key}">${esc(p.label)}</option>`).join('')}</select></div>
          <div class="field"><label>Skala variabel terikat</label><select id="mg-scale">${options.scales.map((s) =>
            `<option value="${s}">${esc(s)}</option>`).join('')}</select></div>
          <div class="field"><label>Jumlah variabel bebas</label>
            <input type="number" id="mg-nx" value="1" min="1" style="width:80px"></div>
          <div class="field"><label>Jumlah kelompok</label>
            <input type="number" id="mg-ng" value="2" min="1" style="width:80px"></div>
          <div class="field"><label>Berpasangan</label><select id="mg-paired">
            <option value="false">tidak</option><option value="true">ya</option></select></div>
          <button class="btn" id="mg-go">Susun rekomendasi</button>
        </div>
        <div id="mg-out" style="margin-top:12px"></div></div>
      <div class="card"><h3>Ukuran sampel</h3>
        <div class="row">
          <div class="field"><label>Jumlah populasi</label>
            <input type="number" id="ss-pop" placeholder="250" style="width:120px"></div>
          <div class="field"><label>Taraf kesalahan</label><select id="ss-e">
            <option value="0.05">5%</option><option value="0.1">10%</option>
            <option value="0.01">1%</option></select></div>
          <div class="field"><label>Variabel bebas</label>
            <input type="number" id="ss-nx" placeholder="3" style="width:110px"></div>
          <button class="btn ghost" id="ss-go">Hitung</button></div>
        <div id="ss-out" style="margin-top:10px"></div></div>`,

    kualitatif: () => `<div class="card"><h3>Pengodean transkrip</h3>
        <p class="hint">Setiap kutipan diverifikasi benar-benar ada di transkrip yang Anda
          ketik. Kutipan yang tidak ditemukan tidak disimpan.</p>
        <div class="row"><div class="field"><label>Transkrip</label>
          <select id="ql-ds">${datasets.filter((d) => d.kind === 'transcript').map((d) =>
            `<option value="${d.id}">${esc(d.filename)}</option>`).join('')
            || '<option value="">— unggah transkrip .txt lebih dahulu —</option>'}</select></div>
          <button class="btn" id="ql-suggest">Usulkan kode awal</button>
          <button class="btn ghost" id="ql-themes">Susun tema & triangulasi</button></div>
        <div id="ql-out" style="margin-top:12px"></div></div>`,

    jejak: () => `<div class="card"><h3>Jejak analisis</h3>
        <p class="hint">Data, langkah, parameter, dan hasil setiap analisis tersimpan agar
          dapat ditelusuri ulang saat ditanya penguji.</p>
        <div class="list">${analyses.map((a) => `<div class="item">
          <strong>${esc(a.result_json.label)}</strong>
          <span class="tag">${esc(a.method)}</span>
          <div class="meta">${esc(a.created_at)} · parameter:
            ${esc(JSON.stringify(a.params_json))}</div>
          <div style="margin-top:6px">${esc((a.narrative || '').slice(0, 320))}…</div>
          <div class="row" style="margin-top:6px">
            <select data-insert-target="${a.id}" style="width:220px">
              ${flatten(S.manuscript.sections).filter((s) => !s.children.length).map((s) =>
                `<option value="${s.id}">${esc(s.number)} ${esc(s.title)}</option>`).join('')}
            </select>
            <button class="btn ghost small" data-insert="${a.id}">Sisipkan ke naskah</button></div>
        </div>`).join('') || '<div class="empty">Belum ada analisis.</div>'}</div></div>`,
  };

  const showTab = (key) => {
    $('#data-body').innerHTML = bodies[key]();
    view().querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.dt === key));
    bindDataTab(key, methods);
  };
  view().querySelectorAll('.tab').forEach((t) => { t.onclick = () => showTab(t.dataset.dt); });
  showTab('uji');
}

const LIST_PARAMS = ['columns', 'items', 'predictors'];

function bindDataTab(key, methods) {
  const pid = S.project.id;

  if (key === 'uji') {
    $('#ds-up').onclick = (e) => run(async () => {
      const file = $('#ds-file').files[0];
      if (!file) return toast('Pilih berkas data lebih dahulu.', true);
      const fd = new FormData(); fd.append('file', file);
      const res = await api(`/projects/${pid}/datasets`, { method: 'POST', body: fd });
      toast(`${res.n_rows} baris × ${res.n_cols} kolom terbaca.`);
      render();
    }, e.currentTarget);

    const columnsOf = async () => {
      const id = Number($('#an-ds').value);
      const dataset = S.datasets.find((d) => d.id === id);
      return dataset?.meta_json?.columns ?? [];
    };
    const renderParams = async () => {
      const method = methods.methods.find((m) => m.key === $('#an-method').value);
      const cols = await columnsOf();
      $('#an-params').innerHTML = method.params.map((p) => {
        if (LIST_PARAMS.includes(p)) {
          return `<div class="field grow"><label>${esc(p)} (pisahkan dengan koma)</label>
            <input type="text" data-param="${p}" placeholder="${cols.slice(0, 3).join(', ')}"></div>`;
        }
        if (['ratings', 'loadings', 'paths'].includes(p)) {
          return `<div class="field grow"><label>${esc(p)} (JSON, tempel dari output perangkat)</label>
            <textarea data-param="${p}" placeholder='${p === 'loadings'
              ? '{"Kepuasan": {"X1": 0.82, "X2": 0.79}}' : '[[4,5,4],[3,4,4]]'}'></textarea></div>`;
        }
        return `<div class="field"><label>${esc(p)}</label><select data-param="${p}">
          ${cols.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}</select></div>`;
      }).join('');
    };
    $('#an-method').onchange = renderParams;
    $('#an-ds').onchange = renderParams;
    renderParams();

    $('#an-run').onclick = (e) => run(async () => {
      const params = {};
      view().querySelectorAll('[data-param]').forEach((el) => {
        const name = el.dataset.param;
        if (LIST_PARAMS.includes(name)) {
          params[name] = el.value.split(',').map((s) => s.trim()).filter(Boolean);
        } else if (['ratings', 'loadings', 'paths'].includes(name)) {
          params[name] = JSON.parse(el.value || (name === 'loadings' ? '{}' : '[]'));
        } else { params[name] = el.value; }
      });
      const res = await api(`/projects/${pid}/analyses`, { method: 'POST', body: {
        method: $('#an-method').value, dataset_id: Number($('#an-ds').value), params } });
      $('#an-out').innerHTML = renderAnalysis(res);
    }, e.currentTarget);
  }

  if (key === 'pemandu') {
    $('#mg-go').onclick = (e) => run(async () => {
      const res = await api('/methodology/recommend', { method: 'POST', body: {
        purpose: $('#mg-purpose').value, dependent_scale: $('#mg-scale').value,
        n_independent: Number($('#mg-nx').value), n_groups: Number($('#mg-ng').value),
        paired: $('#mg-paired').value === 'true' } });
      $('#mg-out').innerHTML = `<div class="note-box ok"><strong>${esc(res.design)}</strong>
        Pendekatan ${esc(res.approach)}</div>
        <table style="margin-top:10px"><tbody>
        <tr><th style="width:170px">Uji yang dijalankan</th><td>${res.tests.map((t) =>
          `<span class="tag">${esc(t)}</span>`).join(' ')}</td></tr>
        <tr><th>Prasyarat</th><td>${res.prerequisites.map(esc).join('<br>')}</td></tr>
        <tr><th>Instrumen</th><td>${esc(res.instrument)}</td></tr>
        <tr><th>Teknik sampling</th><td>${esc(res.sampling)}</td></tr>
        <tr><th>Dasar pemilihan</th><td>${res.reasoning.map(esc).join('<br>')}</td></tr>
        ${res.cautions.length ? `<tr><th>Perhatian</th><td>${res.cautions.map(esc).join('<br>')}</td></tr>` : ''}
        </tbody></table>`;
    }, e.currentTarget);

    $('#ss-go').onclick = (e) => run(async () => {
      const body = { margin_of_error: Number($('#ss-e').value) };
      if ($('#ss-pop').value) body.population = Number($('#ss-pop').value);
      if ($('#ss-nx').value) body.n_predictors = Number($('#ss-nx').value);
      const res = await api('/methodology/sample-size', { method: 'POST', body });
      $('#ss-out').innerHTML = Object.values(res).map((r) =>
        `<div class="note-box ok" style="margin-bottom:6px"><strong>${esc(r.formula)}</strong>
          ${esc(r.narrative)}</div>`).join('');
    }, e.currentTarget);
  }

  if (key === 'kualitatif') {
    $('#ql-suggest').onclick = (e) => run(async () => {
      const dsId = Number($('#ql-ds').value);
      if (!dsId) return toast('Unggah transkrip .txt lebih dahulu.', true);
      const res = await api(`/projects/${pid}/qualitative/suggest`, { method: 'POST', body: {
        dataset_id: dsId } });
      $('#ql-out').innerHTML = `<div class="note-box">${esc(res.note)}
        <span class="meta">${res.n_utterances} giliran bicara terbaca.</span></div>
        <div class="row" style="margin-top:10px">
          <div class="field grow"><label>Kode yang dipakai (pisahkan dengan koma)</label>
            <input type="text" id="ql-codes" value="${res.candidates.slice(0, 6).map((c) => esc(c.code)).join(', ')}"></div>
          <button class="btn" id="ql-apply">Terapkan pengodean</button></div>
        <div class="list" style="margin-top:10px">${res.candidates.map((c) => `<div class="item">
          <span class="tag">${esc(c.kind)}</span> <strong>${esc(c.code)}</strong>
          <span class="meta">muncul ${c.count}×</span></div>`).join('')}</div>`;
      $('#ql-apply').onclick = (ev) => run(async () => {
        const codes = $('#ql-codes').value.split(',').map((s) => s.trim()).filter(Boolean);
        const out = await api(`/projects/${pid}/qualitative/apply`, { method: 'POST', body: {
          dataset_id: dsId, codes } });
        toast(`${out.saved} segmen tersimpan, ${out.rejected} ditolak karena tidak ditemukan di transkrip.`);
      }, ev.currentTarget);
    }, e.currentTarget);

    $('#ql-themes').onclick = (e) => run(async () => {
      const segments = await api(`/projects/${pid}/qualitative/segments`);
      if (!segments.count) return toast('Belum ada segmen berkode.', true);
      const map = {};
      segments.segments.forEach((s) => { map[s.code] = s.theme || `Tema: ${s.code}`; });
      const res = await api(`/projects/${pid}/qualitative/themes`, { method: 'POST', body: { theme_map: map } });
      $('#ql-out').innerHTML = `
        <div class="metrics" style="margin-bottom:12px">
          <div class="metric"><div class="v">${res.n_codes}</div><div class="k">kode</div></div>
          <div class="metric"><div class="v">${res.n_segments}</div><div class="k">segmen</div></div>
          <div class="metric"><div class="v">${res.themes.length}</div><div class="k">tema</div></div>
          <div class="metric"><div class="v">${res.reduction.n_after}</div><div class="k">setelah reduksi</div></div>
        </div>
        ${res.triangulation.single_source_codes.length ? `<div class="note-box warn">
          <strong>Kode yang hanya didukung satu informan</strong>
          ${res.triangulation.single_source_codes.map(esc).join(', ')} — ${esc(res.triangulation.note)}</div>` : ''}
        <div class="scroll-x" style="margin-top:10px"><table>
          <thead><tr>${res.triangulation.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
          <tbody>${res.triangulation.rows.map((r) => `<tr>${r.map((v) =>
            `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }, e.currentTarget);
  }

  if (key === 'jejak') {
    view().querySelectorAll('[data-insert]').forEach((b) => b.onclick = () => run(async () => {
      const target = view().querySelector(`[data-insert-target="${b.dataset.insert}"]`).value;
      const res = await api(`/analyses/${b.dataset.insert}/insert`, { method: 'POST', body: {
        section_id: Number(target) } });
      toast(`${res.inserted} blok disisipkan ke naskah.`);
      await refreshProject(pid);
    }, b));
  }
}

function renderAnalysis(res) {
  const r = res.result;
  return `
    ${res.guardrail && !res.guardrail.allowed ? `<div class="note-box danger">
      <strong>Narasi model ditolak</strong>${esc(res.guardrail.reason)}</div>` : ''}
    ${r.tables.map((t) => `<div style="margin-bottom:12px">
      <div style="font-weight:650;margin-bottom:5px">${esc(t.title)}</div>
      <div class="scroll-x"><table>
        <thead><tr>${t.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${t.rows.map((row) => `<tr>${row.map((v) =>
          `<td>${esc(v ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
      ${t.note ? `<div class="meta" style="margin-top:4px">${esc(t.note)}</div>` : ''}</div>`).join('')}
    ${r.warnings.length ? `<div class="note-box warn"><strong>Catatan</strong>
      ${r.warnings.map(esc).join('<br>')}</div>` : ''}
    <div class="note-box" style="margin-top:10px"><strong>Narasi hasil
      (${esc(res.narrative_source)})</strong>${esc(res.narrative)}</div>`;
}

/* ------------------------------------------------- 7. Periksa naskah */

async function viewChecks() {
  view().innerHTML = `
    <div class="panel">
      <h2>Periksa naskah</h2>
      <p class="sub">Keselarasan rumusan masalah sampai kesimpulan, kelengkapan silang sitasi,
        kaidah PUEBI, serta indikasi kemiripan — sebelum naskah masuk sistem kampus.</p>
      <div class="card"><button class="btn" id="ck-run">Jalankan seluruh pemeriksaan</button>
        <span class="meta" style="margin-left:8px">Berjalan lokal, tidak menagih kredit.</span></div>
      <div id="ck-out">${S.checks ? checksHtml(S.checks) : '<div class="empty">Belum ada pemeriksaan.</div>'}</div>
    </div>`;

  $('#ck-run').onclick = (e) => run(async () => {
    S.checks = await api(`/projects/${S.project.id}/checks`, { method: 'POST' });
    $('#ck-out').innerHTML = checksHtml(S.checks);
  }, e.currentTarget);
}

function checksHtml(data) {
  const c = data.checks;
  const s = data.summary;
  return `
    <div class="card"><h3>Ringkasan</h3>
      <div class="note-box ${s.ready_to_submit ? 'ok' : 'warn'}" style="margin-bottom:10px">
        <strong>${s.ready_to_submit ? 'Naskah lolos seluruh pemeriksaan' : 'Masih ada yang perlu dibereskan'}</strong>
        ${s.areas.map((a) => `${esc(a.kind)}: ${a.count} temuan${a.critical ? ` (${a.critical} berat)` : ''}`).join(' · ')}
      </div>
      <div class="metrics">${s.areas.map((a) => `<div class="metric">
        <div class="v">${a.percent !== undefined ? a.percent + '%' : a.count}</div>
        <div class="k">${esc(a.kind)} ${a.passed ? '<span class="tag ok">lolos</span>' : '<span class="tag warn">periksa</span>'}</div>
      </div>`).join('')}</div></div>

    ${c.bahasa ? `<div class="card"><h3>Bahasa akademik Indonesia — ${c.bahasa.total} temuan</h3>
      <div class="meta" style="margin-bottom:8px">${num(c.bahasa.word_count)} kata,
        ${num(c.bahasa.sentence_count)} kalimat.</div>
      ${c.bahasa.findings.slice(0, 25).map((f) => `<div class="finding ${f.severity}">
        <strong>${esc(f.rule)}</strong> · ${esc(f.section_title)} — ${esc(f.message)}
        <span class="ex">${esc(f.excerpt)}</span>
        <span class="sug">→ ${esc(f.suggestion)}</span></div>`).join('')}
      ${c.bahasa.total > 25 ? `<div class="meta">…dan ${c.bahasa.total - 25} temuan lain.</div>` : ''}</div>` : ''}

    ${c.sitasi ? `<div class="card"><h3>Cek silang sitasi</h3>
      <div class="metrics" style="margin-bottom:10px">
        <div class="metric"><div class="v">${c.sitasi.n_references}</div><div class="k">referensi</div></div>
        <div class="metric"><div class="v">${c.sitasi.n_citations_in_text}</div><div class="k">sitasi dalam teks</div></div>
        <div class="metric"><div class="v">${c.sitasi.dangling.length}</div><div class="k">sitasi menggantung</div></div>
        <div class="metric"><div class="v">${c.sitasi.uncited.length}</div><div class="k">referensi tak dikutip</div></div>
        <div class="metric"><div class="v">${c.sitasi.recency.recent}</div>
          <div class="k">terbit ≤ ${c.sitasi.recency.window_years} thn</div></div>
      </div>
      ${c.sitasi.issues.map((i) => `<div class="finding ${i.severity}">${esc(i.message)}</div>`).join('')
        || '<div class="note-box ok">Seluruh sitasi sinkron dengan daftar pustaka.</div>'}</div>` : ''}

    ${c.konsistensi ? `<div class="card"><h3>Cek konsistensi</h3>
      <div class="meta" style="margin-bottom:8px">Butir terbaca:
        ${Object.entries(c.konsistensi.counts).map(([k, v]) => `${esc(k)} ${v}`).join(' · ') || '—'}</div>
      ${c.konsistensi.issues.map((i) => `<div class="finding ${i.severity}">${esc(i.message)}
        ${i.detail ? `<span class="ex">${esc(i.detail)}</span>` : ''}</div>`).join('')
        || '<div class="note-box ok">Rumusan masalah, tujuan, dan simpulan sudah selaras.</div>'}</div>` : ''}

    ${c.kemiripan ? `<div class="card"><h3>Cek kemiripan mandiri — ${c.kemiripan.similarity_percent}%</h3>
      <div class="note-box" style="margin-bottom:10px">${esc(c.kemiripan.scope_note)}</div>
      ${c.kemiripan.matches.slice(0, 10).map((m) => `<div class="finding sedang">
        <strong>${m.n_words} kata mirip</strong> dengan
        <span class="cite-chip">${esc(m.citekey)}</span>
        ${m.page ? `hlm. ${m.page}` : ''} · ${esc(m.section_title)}
        <span class="ex">${esc(m.text.slice(0, 220))}…</span>
        <span class="sug">→ ${esc(m.guidance)}</span></div>`).join('')
        || '<div class="note-box ok">Tidak ditemukan rentang yang mirip dengan sumber di pustaka.</div>'}</div>` : ''}

    ${c.batas ? `<div class="card"><h3>Cek batas panjang</h3>
      <div class="metrics" style="margin-bottom:10px">
        <div class="metric"><div class="v">${num(c.batas.total_words)}</div><div class="k">kata</div></div>
        <div class="metric"><div class="v">${c.batas.estimated_pages}</div><div class="k">perkiraan halaman</div></div>
        <div class="metric"><div class="v">${c.batas.max_words ? num(c.batas.max_words) : '—'}</div><div class="k">batas kata</div></div>
        <div class="metric"><div class="v">${c.batas.max_pages ?? '—'}</div><div class="k">batas halaman</div></div>
      </div>
      ${c.batas.issues.map((i) => `<div class="finding ${i.severity}">${esc(i.message)}</div>`).join('')
        || '<div class="note-box ok">Panjang naskah masih dalam batas.</div>'}
      <div class="scroll-x" style="margin-top:10px"><table>
        <thead><tr><th>Bagian</th><th>Kata</th><th>Target</th><th>Halaman</th><th>Status</th></tr></thead>
        <tbody>${c.batas.sections.filter((x) => x.word_count).map((x) => `<tr>
          <td>${esc(x.number)} ${esc(x.title)}</td><td>${num(x.word_count)}</td>
          <td>${num(x.target_words)}</td><td>${x.estimated_pages}</td>
          <td><span class="tag ${x.status === 'sesuai' ? 'ok' : 'warn'}">${esc(x.status)}</span></td>
        </tr>`).join('')}</tbody></table></div></div>` : ''}`;
}

/* ------------------------------------------------- 8. Ekspor & revisi */

async function viewExport() {
  const [revisions, supervision, submissions] = await Promise.all([
    api(`/projects/${S.project.id}/revisions`),
    api(`/projects/${S.project.id}/supervision`),
    api(`/projects/${S.project.id}/submissions`),
  ]);
  const d = S.project.work_type_detail;

  view().innerHTML = `
    <div class="panel" style="max-width:1100px">
      <h2>Ekspor & kelola revisi</h2>
      <p class="sub">Naskah diekspor dalam keadaan sudah terformat penuh. Catatan dosen maupun
        reviewer dicatat sebagai daftar tugas berstatus.</p>

      <div class="card"><h3>Ekspor naskah</h3>
        <div class="row">
          <div class="field"><label>Penulis</label><input type="text" id="ex-author" placeholder="Nama lengkap"></div>
          <div class="field"><label>NIM</label><input type="text" id="ex-nim" style="width:120px"></div>
          <div class="field grow"><label>Institusi</label><input type="text" id="ex-inst" placeholder="Universitas …"></div>
          <div class="field grow"><label>Fakultas / Program studi</label><input type="text" id="ex-fak"></div>
        </div>
        <div class="row" style="margin-top:10px">
          ${d.export_formats.map((f) => `<button class="btn" data-export="${f}">Ekspor ${f.toUpperCase()}</button>`).join('')}
        </div>
        <div id="ex-out" style="margin-top:12px"></div></div>

      <div class="card"><h3>Pelacak bimbingan — ${revisions.total} revisi</h3>
        <p class="hint">Coretan dosen — komentar PDF atau dokumen Word bertanda — diubah
          menjadi daftar revisi berstatus yang terhubung ke lokasinya di naskah.</p>
        <div class="row" style="margin-bottom:10px">
          <div class="field grow"><label>Impor berkas bertanda (.pdf / .docx)</label>
            <input type="file" id="rv-file" accept=".pdf,.docx"></div>
          <div class="field"><label>Sumber</label><select id="rv-fsrc">
            <option value="pembimbing">Pembimbing</option><option value="penguji">Penguji</option>
            <option value="reviewer">Reviewer</option></select></div>
          <button class="btn ghost" id="rv-import">Impor komentar</button></div>
        <div id="rv-import-out" style="margin-bottom:10px"></div>
        <div class="row" style="margin-bottom:10px">
          <div class="field grow"><label>Catatan pembimbing / reviewer</label>
            <input type="text" id="rv-text" placeholder="Perbaiki rumusan masalah nomor 2 agar sejalan dengan tujuan"></div>
          <div class="field"><label>Sumber</label><select id="rv-src">
            <option value="pembimbing">Pembimbing</option><option value="penguji">Penguji</option>
            <option value="reviewer">Reviewer</option><option value="mandiri">Mandiri</option></select></div>
          <div class="field"><label>Bagian</label><select id="rv-sec"><option value="">— tidak spesifik —</option>
            ${flatten(S.manuscript.sections).map((s) =>
              `<option value="${s.id}">${esc(s.number)} ${esc(s.title)}</option>`).join('')}</select></div>
          <button class="btn" id="rv-add">Catat</button></div>
        <div class="list">${revisions.revisions.map((r) => `<div class="item">
          <div style="display:flex;justify-content:space-between;gap:10px">
            <div><strong>${esc(r.text)}</strong>
              <div class="meta"><span class="tag">${esc(r.source)}</span>
                ${r.section_title ? esc(r.section_title) : 'tanpa bagian'} · ${esc(r.created_at)}</div></div>
            <select data-rvstatus="${r.id}" style="width:130px">
              ${['terbuka', 'dikerjakan', 'selesai', 'ditolak'].map((s) =>
                `<option value="${s}" ${r.status === s ? 'selected' : ''}>${s}</option>`).join('')}
            </select></div></div>`).join('') || '<div class="empty">Belum ada revisi tercatat.</div>'}</div></div>

      ${d.supervision_tracking ? `<div class="card"><h3>Riwayat bimbingan</h3>
        <div class="row" style="margin-bottom:10px">
          <div class="field"><label>Tanggal</label><input type="date" id="sv-date"></div>
          <div class="field"><label>Pembimbing</label><input type="text" id="sv-name" style="width:150px"></div>
          <div class="field grow"><label>Catatan & capaian</label><input type="text" id="sv-notes"></div>
          <button class="btn ghost" id="sv-add">Catat sesi</button></div>
        <div class="list">${supervision.map((s) => `<div class="item">
          <strong>${esc(s.met_on)}</strong> ${esc(s.supervisor || '')}
          <div class="meta">${esc(s.notes)}</div></div>`).join('')
          || '<div class="empty">Belum ada sesi bimbingan.</div>'}</div></div>` : ''}

      ${d.defense_mode ? `<div class="card"><h3>Mode siap sidang</h3>
        <p class="hint">Pertanyaan penguji disusun dari titik yang benar-benar rawan pada naskah.</p>
        <button class="btn" id="df-go">Susun kemungkinan pertanyaan</button>
        <div id="df-out" style="margin-top:12px"></div></div>` : ''}

      ${d.family !== 'artikel_publikasi' ? `<div class="card"><h3>Konversi naskah menjadi artikel</h3>
        <p class="hint">Memadatkan tugas akhir menjadi artikel berstruktur IMRAD tanpa
          kehilangan temuan utamanya. Rencananya ditampilkan lebih dahulu.</p>
        <div class="row">
          <div class="field"><label>Target kata artikel</label>
            <input type="number" id="cv-target" value="6000" style="width:120px"></div>
          <button class="btn ghost" id="cv-plan">Lihat rencana</button>
          <button class="btn" id="cv-apply">Bangun proyek artikel</button></div>
        <div id="cv-out" style="margin-top:12px"></div></div>` : ''}

      <div class="card"><h3>Jurnal tujuan</h3>
        <p class="hint">Naskah tidak ditolak di meja editor hanya karena salah format.</p>
        <div class="row">
          <div class="field grow"><label>Profil jurnal</label>
            <select id="jr-profile"><option value="">memuat…</option></select></div>
          <button class="btn ghost" id="jr-check">Periksa kesiapan</button>
          <button class="btn ghost" id="jr-apply">Jadikan aturan naskah</button></div>
        <div id="jr-out" style="margin-top:12px"></div></div>

      <div class="card"><h3>Dua bahasa</h3>
        <p class="hint">Penerjemahan yang menjaga konsistensi istilah teknis per bidang ilmu —
          menjawab kewajiban abstrak dwibahasa.</p>
        <div class="field"><label>Teks bahasa Indonesia</label>
          <textarea id="tr-id" placeholder="Penelitian ini menguji pengaruh motivasi kerja terhadap kinerja karyawan…"></textarea></div>
        <div class="row" style="margin-top:8px">
          <button class="btn ghost" id="tr-go">Terjemahkan ke Inggris</button>
          <button class="btn ghost" id="tr-glossary">Lihat padanan istilah</button></div>
        <div class="field" style="margin-top:10px"><label>Versi bahasa Inggris (untuk diperiksa)</label>
          <textarea id="tr-en" placeholder="This study examines the effect of work motivation on employee performance…"></textarea></div>
        <button class="btn ghost" id="tr-check" style="margin-top:8px">Periksa konsistensi istilah</button>
        <div id="tr-out" style="margin-top:12px"></div></div>

      ${d.submission_kit ? `<div class="card"><h3>Berkas submisi</h3>
        <div class="row">
          <div class="field grow"><label>Jurnal tujuan</label>
            <input type="text" id="pb-journal" placeholder="Jurnal Manajemen Indonesia"></div>
          <button class="btn ghost" id="pb-abstract">Abstrak terstruktur</button>
          <button class="btn ghost" id="pb-cover">Cover letter</button></div>
        <div id="pb-out" style="margin-top:12px"></div></div>` : ''}

      ${submissions.length ? `<div class="card"><h3>Berkas tersimpan</h3>
        <div class="list">${submissions.map((s) => `<div class="item">
          <span class="tag">${esc(s.kind)}</span> ${esc(s.venue || '')}
          <pre class="out" style="margin-top:6px">${esc(s.content.slice(0, 700))}</pre></div>`).join('')}</div></div>` : ''}
    </div>`;

  view().querySelectorAll('[data-export]').forEach((b) => b.onclick = () => run(async () => {
    const res = await api(`/projects/${S.project.id}/export`, { method: 'POST', body: {
      format: b.dataset.export,
      meta: { author: $('#ex-author').value, student_id: $('#ex-nim').value,
        institution: $('#ex-inst').value, faculty: $('#ex-fak').value } } });
    const r = res.applied_rules;
    $('#ex-out').innerHTML = `<div class="note-box ok">
      <strong>${res.format.toUpperCase()} dirakit — ${num(res.size_bytes / 1024, 1)} KB</strong>
      Aturan yang diterapkan: ${esc(r.font)}, spasi ${r.line_spacing},
      margin ${r.margins.top_cm}/${r.margins.right_cm}/${r.margins.bottom_cm}/${r.margins.left_cm} cm,
      ${esc(r.citation_style)}, halaman awal ${esc(r.front_matter_numbering)} → isi ${esc(r.body_numbering)}.
      ${res.assumed_rules?.length ? `<div class="meta" style="margin-top:6px">Memakai bawaan:
        ${res.assumed_rules.map(esc).join(', ')}</div>` : ''}
      <a class="btn small" style="margin-top:8px;display:inline-block;text-decoration:none"
         href="/api${res.download_url.replace('/api', '')}">Unduh berkas</a></div>`;
  }, b));

  $('#rv-add').onclick = (e) => run(async () => {
    const text = $('#rv-text').value.trim();
    if (!text) return toast('Catatan masih kosong.', true);
    await api(`/projects/${S.project.id}/revisions`, { method: 'POST', body: {
      text, source: $('#rv-src').value, section_id: $('#rv-sec').value ? Number($('#rv-sec').value) : null } });
    render();
  }, e.currentTarget);

  view().querySelectorAll('[data-rvstatus]').forEach((sel) => sel.onchange = () => run(async () => {
    await api(`/revisions/${sel.dataset.rvstatus}`, { method: 'PATCH', body: { status: sel.value } });
    toast('Status revisi diperbarui.');
  }));

  if ($('#sv-add')) $('#sv-add').onclick = (e) => run(async () => {
    if (!$('#sv-date').value) return toast('Tanggal bimbingan belum diisi.', true);
    await api(`/projects/${S.project.id}/supervision`, { method: 'POST', body: {
      met_on: $('#sv-date').value, supervisor: $('#sv-name').value, notes: $('#sv-notes').value } });
    render();
  }, e.currentTarget);

  if ($('#df-go')) $('#df-go').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/defense`, { method: 'POST' });
    $('#df-out').innerHTML = `
      ${res.weak_points.length ? `<div class="note-box warn" style="margin-bottom:10px">
        <strong>${res.weak_points.length} titik rawan terdeteksi pada naskah</strong>
        ${res.weak_points.slice(0, 5).map((w) => esc(w.message)).join('<br>')}</div>` : ''}
      <div class="list">${res.questions.map((q) => `<div class="item">
        <strong>${esc(q.pertanyaan)}</strong>
        <span class="tag ${q.tingkat_risiko === 'tinggi' ? 'danger' : 'warn'}">${esc(q.tingkat_risiko)}</span>
        <div class="meta">Sasaran: ${esc(q.sasaran)}</div>
        <div style="margin-top:4px">${esc(q.kerangka_jawaban)}</div></div>`).join('')}</div>`;
  }, e.currentTarget);

  $('#rv-import').onclick = (e) => run(async () => {
    const file = $('#rv-file').files[0];
    if (!file) return toast('Pilih berkas bertanda lebih dahulu.', true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('source', $('#rv-fsrc').value);
    const res = await api(`/projects/${S.project.id}/revisions/import`, { method: 'POST', body: fd });
    $('#rv-import-out').innerHTML = `<div class="note-box ${res.count ? 'ok' : 'warn'}">
      <strong>${res.count} komentar terbaca — ${res.linked} tertaut ke bagian naskah,
        ${res.created} dicatat sebagai revisi</strong>
      ${res.notes.map(esc).join('<br>')}</div>
      <div class="list" style="margin-top:8px">${res.comments.map((c) => `<div class="item">
        <span class="tag">${esc(c.kind)}</span>
        ${c.page ? `<span class="tag">hlm. ${c.page}</span>` : ''}
        ${c.section_title ? `<span class="tag ok">${esc(c.section_title)}</span>`
          : '<span class="tag warn">tanpa lokasi</span>'}
        <div style="margin-top:4px">${esc(c.text)}</div>
        ${c.anchor ? `<div class="meta" style="margin-top:3px">menyorot: “${esc(c.anchor.slice(0, 140))}”</div>` : ''}
      </div>`).join('')}</div>`;
    if (res.created) setTimeout(render, 1200);
  }, e.currentTarget);

  if ($('#cv-plan')) $('#cv-plan').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/conversion/plan`, { method: 'POST', body: {
      target_words: Number($('#cv-target').value) } });
    $('#cv-out').innerHTML = conversionHtml(res);
  }, e.currentTarget);

  if ($('#cv-apply')) $('#cv-apply').onclick = (e) => run(async () => {
    if (!confirm('Bangun proyek artikel baru dari naskah ini? Naskah asli tidak diubah.')) return;
    const res = await api(`/projects/${S.project.id}/conversion/apply`, { method: 'POST', body: {
      target_words: Number($('#cv-target').value) } });
    S.projects = await api('/projects');
    $('#cv-out').innerHTML = `<div class="note-box ok">
      <strong>Proyek artikel dibuat — ${res.sections_created} bagian,
        ${res.references_copied} referensi ikut pindah</strong>${esc(res.note)}
      <button class="btn small" id="cv-open" style="margin-top:8px">Buka proyek artikel</button></div>
      ${conversionHtml(res.plan)}`;
    $('#cv-open').onclick = () => run(async () => {
      S.sectionId = null;
      await refreshProject(res.project_id);
      syncPicker(); S.view = 'menulis'; render();
    });
  }, e.currentTarget);

  api('/journals').then((data) => {
    const sel = $('#jr-profile');
    if (!sel) return;
    sel.innerHTML = data.profiles.map((p) =>
      `<option value="${p.key}">${esc(p.name)}</option>`).join('');
  });

  if ($('#jr-check')) $('#jr-check').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/journal/readiness`, { method: 'POST', body: {
      profile: $('#jr-profile').value } });
    const p = res.profile_detail;
    $('#jr-out').innerHTML = `
      <div class="note-box ${res.ready ? 'ok' : 'warn'}">
        <strong>${res.ready ? 'Struktur dan batas panjang sudah sesuai' : 'Belum siap dikirim'}</strong>
        ${res.word_count} kata${p.max_words ? ` dari batas ${num(p.max_words)}` : ''} ·
        gaya sitasi ${esc(p.citation_style.toUpperCase())}
        ${p.abstract_max_words ? ` · abstrak maks. ${p.abstract_max_words} kata` : ''}</div>
      <div class="row" style="margin:8px 0">
        ${res.matched_sections.map((s) => `<span class="tag ok">${esc(s)}</span>`).join(' ')}
        ${res.missing_sections.map((s) => `<span class="tag danger">kurang: ${esc(s)}</span>`).join(' ')}
        ${res.extra_sections.map((s) => `<span class="tag warn">lebih: ${esc(s)}</span>`).join(' ')}</div>
      ${res.issues.map((i) => `<div class="finding ${i.severity}">${esc(i.message)}</div>`).join('')}
      ${p.notes.length ? `<div class="note-box" style="margin-top:8px">
        ${p.notes.map(esc).join('<br>')}</div>` : ''}`;
  }, e.currentTarget);

  if ($('#jr-apply')) $('#jr-apply').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/journal/apply`, { method: 'POST', body: {
      profile: $('#jr-profile').value } });
    $('#jr-out').innerHTML = `<div class="note-box ok"><strong>Aturan naskah diperbarui</strong>
      ${esc(res.note)}</div>`;
    await refreshProject(S.project.id);
  }, e.currentTarget);

  if ($('#tr-go')) $('#tr-go').onclick = (e) => run(async () => {
    const text = $('#tr-id').value.trim();
    if (!text) return toast('Teks bahasa Indonesia masih kosong.', true);
    const res = await api(`/projects/${S.project.id}/translate`, { method: 'POST', body: {
      text, direction: 'id-en' } });
    if (res.text) $('#tr-en').value = res.text;
    $('#tr-out').innerHTML = res.text
      ? `<div class="note-box ok"><strong>Terjemahan (${esc(res.source)})</strong>${esc(res.text)}
         ${res.meta.note ? `<div class="meta" style="margin-top:6px">${esc(res.meta.note)}</div>` : ''}</div>`
      : `<div class="note-box warn"><strong>${esc(res.meta.note || '')}</strong>
         <pre class="out" style="margin-top:6px">${esc(res.meta.glossary || '')}</pre></div>`;
  }, e.currentTarget);

  if ($('#tr-glossary')) $('#tr-glossary').onclick = (e) => run(async () => {
    const field = S.project.field_of_study || '';
    const res = await api(`/glossary?field_of_study=${encodeURIComponent(field)}`);
    const entries = Object.entries(res.terms);
    $('#tr-out').innerHTML = `<div class="note-box">
      <strong>${res.count} padanan istilah${field ? ` (termasuk bidang ${esc(field)})` : ''}</strong>
      Bidang tersedia: ${res.fields_available.map(esc).join(', ')}</div>
      <div class="scroll-x" style="margin-top:8px;max-height:300px;overflow-y:auto"><table>
      <thead><tr><th>Indonesia</th><th>Inggris</th></tr></thead><tbody>
      ${entries.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}
      </tbody></table></div>`;
  }, e.currentTarget);

  if ($('#tr-check')) $('#tr-check').onclick = (e) => run(async () => {
    const indonesian = $('#tr-id').value.trim();
    const english = $('#tr-en').value.trim();
    if (!indonesian || !english) return toast('Isi kedua versi teks lebih dahulu.', true);
    const res = await api(`/projects/${S.project.id}/terminology`, { method: 'POST', body: {
      indonesian, english } });
    $('#tr-out').innerHTML = `<div class="note-box ${res.passed ? 'ok' : 'warn'}">
      <strong>${res.terms_consistent} dari ${res.terms_detected} istilah teknis konsisten</strong>
      ${res.passed ? 'Seluruh padanan sudah sesuai glosarium.'
        : 'Istilah di bawah perlu disamakan agar tidak terbaca sebagai ketidakcermatan.'}</div>
      ${res.issues.map((i) => `<div class="finding sedang">${esc(i.message)}</div>`).join('')}`;
  }, e.currentTarget);

  if ($('#pb-abstract')) $('#pb-abstract').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/abstract`, { method: 'POST', body: {} });
    $('#pb-out').innerHTML = `<div class="note-box"><strong>Abstrak terstruktur
      (${esc(res.source)})</strong><pre class="out">${esc(res.text)}</pre></div>`;
  }, e.currentTarget);

  if ($('#pb-cover')) $('#pb-cover').onclick = (e) => run(async () => {
    const res = await api(`/projects/${S.project.id}/cover-letter`, { method: 'POST', body: {
      journal: $('#pb-journal').value || '[Nama Jurnal]', author: $('#ex-author')?.value || '' } });
    $('#pb-out').innerHTML = `<div class="note-box"><strong>Cover letter
      (${esc(res.source)})</strong><pre class="out">${esc(res.text)}</pre></div>`;
  }, e.currentTarget);
}

function conversionHtml(plan) {
  return `
    <div class="metrics" style="margin-bottom:10px">
      <div class="metric"><div class="v">${num(plan.source_words)}</div><div class="k">kata naskah asal</div></div>
      <div class="metric"><div class="v">${num(plan.target_words)}</div><div class="k">target artikel</div></div>
      <div class="metric"><div class="v">${plan.overall_compression <= 1
        ? Math.round(plan.overall_compression * 100) + '%' : '—'}</div>
        <div class="k">${plan.overall_compression <= 1 ? 'tersisa setelah dipadatkan'
          : 'naskah lebih pendek dari target'}</div></div>
      <div class="metric"><div class="v">${plan.citekeys.length}</div><div class="k">sitasi ikut</div></div>
    </div>
    ${plan.warnings.map((w) => `<div class="finding sedang">${esc(w)}</div>`).join('')}
    <div class="scroll-x" style="margin-top:8px"><table>
      <thead><tr><th>Bagian artikel</th><th style="width:90px">Anggaran</th>
        <th style="width:90px">Dari</th><th>Bahan dari naskah</th></tr></thead>
      <tbody>${plan.sections.map((s) => `<tr>
        <td><strong>${esc(s.target)}</strong></td>
        <td>${num(s.target_words)} kata</td>
        <td>${num(s.source_words)} kata</td>
        <td>${s.sources.map((x) => `<span class="tag">${esc(x.number)} ${esc(x.title)}</span>`).join(' ')
          || '<span class="meta">belum ada bahan</span>'}</td></tr>`).join('')}</tbody></table></div>
    ${plan.dropped.length ? `<div class="note-box warn" style="margin-top:10px">
      <strong>Tidak dibawa ke artikel</strong>
      ${plan.dropped.map((d) => `${esc(d.title)} (${d.word_count} kata) — ${esc(d.reason)}`).join('<br>')}</div>` : ''}`;
}

/* ------------------------------------------------- Dashboard & batas */

async function viewDashboard() {
  if (!S.project) { view().innerHTML = '<div class="panel"><div class="empty">Pilih proyek lebih dahulu.</div></div>'; return; }
  const d = await api(`/projects/${S.project.id}/dashboard`);
  view().innerHTML = `
    <div class="panel">
      <h2>Dashboard progres</h2>
      <p class="sub">Status tiap bab, jumlah kata, dan sisa waktu menuju target sidang.</p>
      <div class="card"><div class="metrics">
        <div class="metric"><div class="v">${num(d.word_count)}</div><div class="k">kata tertulis</div></div>
        <div class="metric"><div class="v">${Math.round(d.progress * 100)}%</div><div class="k">dari target</div></div>
        <div class="metric"><div class="v">${num(d.remaining_words)}</div><div class="k">kata tersisa</div></div>
        <div class="metric"><div class="v">${d.days_left ?? '—'}</div><div class="k">hari menuju target</div></div>
        <div class="metric"><div class="v">${d.words_per_day_needed ?? '—'}</div><div class="k">kata/hari dibutuhkan</div></div>
      </div></div>
      <div class="card"><h3>Kemajuan per bab</h3>
        <div class="scroll-x"><table>
          <thead><tr><th>Bab</th><th style="width:90px">Kata</th><th style="width:90px">Target</th>
            <th style="width:150px">Kemajuan</th><th style="width:90px">Status</th></tr></thead>
          <tbody>${d.chapters.map((c) => `<tr><td>${esc(c.number)} ${esc(c.title)}</td>
            <td>${num(c.word_count)}</td><td>${num(c.target_words)}</td>
            <td><div class="bar"><i style="width:${Math.min(100, c.progress * 100)}%"></i></div></td>
            <td><span class="tag ${c.status === 'selesai' ? 'ok' : ''}">${esc(c.status)}</span></td>
          </tr>`).join('')}</tbody></table></div></div>
      <div class="card"><h3>Revisi</h3>
        ${Object.keys(d.revisions).length ? Object.entries(d.revisions).map(([k, v]) =>
          `<span class="tag ${k === 'selesai' ? 'ok' : 'warn'}">${esc(k)}: ${v}</span>`).join(' ')
          : '<div class="meta">Belum ada revisi tercatat.</div>'}</div>
    </div>`;
}

async function viewLimits() {
  const data = await api('/limits');
  const plans = await api('/plans');
  view().innerHTML = `
    <div class="panel">
      <h2>Batas produk</h2>
      <p class="sub">${esc(data.note)}</p>
      <div class="card"><div class="scroll-x"><table>
        <thead><tr><th>Yang dilakukan Recens</th><th>Yang tidak dilakukan Recens</th></tr></thead>
        <tbody>${data.limits.map((l) => `<tr><td>${esc(l.does)}</td>
          <td>${esc(l.does_not)}<div class="meta">aturan: ${esc(l.rule)}</div></td></tr>`).join('')}
        </tbody></table></div></div>
      <div class="card"><h3>Paket akses</h3>
        <div class="note-box" style="margin-bottom:10px">${esc(plans.principle)}</div>
        <div class="scroll-x"><table>
          <thead><tr><th>Paket</th><th>Cocok untuk</th><th>Kuota</th><th>Durasi</th><th>Akses fitur</th></tr></thead>
          <tbody>${plans.plans.map((p) => `<tr><td><strong>${esc(p.label)}</strong></td>
            <td>${esc(p.suitable_for)}</td><td>${num(p.credits)} kredit${p.project_limit
              ? `, ${p.project_limit} proyek` : ', proyek tak terbatas'}</td>
            <td>${p.duration_days ? p.duration_days + ' hari' : '—'}</td>
            <td>${esc(p.feature_access)}</td></tr>`).join('')}</tbody></table></div>
        <div class="meta" style="margin-top:8px">Berjalan lokal tanpa menagih kredit:
          ${plans.free_actions.map((a) => `<span class="tag">${esc(a)}</span>`).join(' ')}</div></div>
    </div>`;
}

/* ------------------------------------------------- boot */

function syncPicker() {
  const picker = $('#project-picker');
  picker.innerHTML = '<option value="">— pilih proyek —</option>' + S.projects.map((p) =>
    `<option value="${p.id}" ${S.project?.id === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
  picker.onchange = () => run(async () => {
    if (!picker.value) { S.project = null; render(); return; }
    S.sectionId = null;
    await refreshProject(Number(picker.value));
    render();
  });
}

(async function boot() {
  try {
    const [catalog, projects, health] = await Promise.all([
      api('/catalog'), api('/projects'), api('/health'),
    ]);
    S.catalog = catalog;
    S.projects = projects;
    const llm = health.language_model;
    const pill = $('#llm-status');
    pill.className = `status-pill ${llm.available ? 'on' : 'off'}`;
    pill.textContent = llm.available ? `model: ${llm.fast_model}` : 'jalur deterministik';
    pill.title = llm.note;

    if (projects.length) await refreshProject(projects[0].id);
    syncPicker();
    render();
  } catch (error) {
    view().innerHTML = `<div class="panel"><div class="note-box danger">
      <strong>Gagal memuat aplikasi</strong>${esc(error.message)}</div></div>`;
  }
})();
