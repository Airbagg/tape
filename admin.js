
// ── Auth ──────────────────────────────────────────────────
(async()=>{
  const t=localStorage.getItem('tape_token');
  if(!t){location.href='/login.html';return}
  const r=await fetch('/api/auth/me',{headers:{Authorization:'Bearer '+t}});
  if(!r.ok){location.href='/login.html';return}
  const u=await r.json();
  if(u.role!=='admin'){location.href='/login.html';return}
})();
const _oF=window.fetch;
window.fetch=(url,opts={})=>{
  if(typeof url==='string'&&url.startsWith('/')){opts.headers={...(opts.headers||{}),Authorization:'Bearer '+localStorage.getItem('tape_token')}}
  return _oF(url,opts)
};
function logout(){localStorage.removeItem('tape_token');localStorage.removeItem('tape_role');location.href='/login.html'}

// ── State ─────────────────────────────────────────────────
let _artistsDB=[], _libData={}, _photoTab='url', _editingArtist=null;
let _pendingDisable=null;
let _editingAlbumId=null, _albumCoverTab='url';
let _editingUserId=null, _allUsers=[], _banType='email';
let _pendingGrantUid=null, _pendingBanUid=null;

// ── Toast ─────────────────────────────────────────────────
function toast(msg,type='success'){
  const el=document.getElementById('toast');
  el.textContent=msg;el.className=`toast ${type} show`;
  setTimeout(()=>el.classList.remove('show'),2500);
}

// ── Navigation ────────────────────────────────────────────
function showPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  document.getElementById('nav-'+name).classList.add('active');
  if(name==='tracks')loadTracksAdmin();
  if(name==='users')loadUsers();
  if(name==='stats')loadStats();
}

// ── Stats ──────────────────────────────────────────────────
async function loadStats(){
  try{
    const s=await fetch('/api/stats').then(r=>r.json());

    // KPI cards
    document.getElementById('kpi-revenue').textContent=s.revenue?`${s.revenue.toLocaleString('ru')}₽`:'0₽';
    document.getElementById('kpi-subs').textContent=s.active_subs;
    document.getElementById('kpi-subs-sub').textContent=`${s.expired_users} истёкших`;
    document.getElementById('kpi-online').textContent=s.online_users;
    document.getElementById('kpi-users').textContent=s.total_users;
    document.getElementById('kpi-users-sub').textContent=`+${s.new_today} сегодня · +${s.new_week} за неделю`;
    document.getElementById('kpi-trial').textContent=s.trial_users;
    document.getElementById('kpi-banned').textContent=s.banned_users;

    // Lib
    document.getElementById('kpi-artists').textContent=s.total_artists;
    document.getElementById('kpi-albums').textContent=s.total_albums;
    document.getElementById('kpi-tracks').textContent=s.total_tracks;

    // Chart: регистрации
    const maxR=Math.max(1,...s.registrations_7d.map(d=>d.count));
    document.getElementById('chart-regs').innerHTML=s.registrations_7d.map(d=>{
      const h=Math.max(4,Math.round((d.count/maxR)*76));
      const label=new Date(d.ts*1000).toLocaleDateString('ru',{day:'2-digit',month:'2-digit'});
      return`<div class="bar-col">
        <div style="font-size:8px;color:var(--muted);min-height:14px">${d.count||''}</div>
        <div class="bar-fill reg" style="height:${h}px"></div>
        <div class="bar-label">${label}</div>
      </div>`;
    }).join('');

    // Chart: подписки
    const maxS=Math.max(1,...s.subscriptions_7d.map(d=>d.count));
    document.getElementById('chart-subs').innerHTML=s.subscriptions_7d.map(d=>{
      const h=Math.max(4,Math.round((d.count/maxS)*76));
      const label=new Date(d.ts*1000).toLocaleDateString('ru',{day:'2-digit',month:'2-digit'});
      return`<div class="bar-col">
        <div style="font-size:8px;color:var(--muted);min-height:14px">${d.count||''}</div>
        <div class="bar-fill sub" style="height:${h}px"></div>
        <div class="bar-label">${label}</div>
      </div>`;
    }).join('');

    // Последние гранты
    if(s.recent_grants.length===0){
      document.getElementById('grants-list').innerHTML='<div class="empty">Грантов пока нет</div>';
    } else {
      document.getElementById('grants-list').innerHTML=s.recent_grants.map(g=>`
        <div class="grant-row">
          <div class="grant-email">${g.email}</div>
          <span class="grant-days">+${g.days}д</span>
          ${g.amount?`<div class="grant-amount">${g.amount}₽</div>`:''}
          <div class="grant-date">${fmtDate(g.created_at)}</div>
        </div>`).join('');
    }
  }catch(e){toast('Ошибка загрузки статистики','error')}
}

// ── Helpers ───────────────────────────────────────────────
function escJ(s){return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'")}
function fmtDate(ts){if(!ts)return'—';return new Date(ts*1000).toLocaleDateString('ru',{day:'2-digit',month:'2-digit',year:'numeric'})}
function fmtDatetime(ts){if(!ts)return'—';return new Date(ts*1000).toLocaleString('ru',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}
function typeBadge(t){
  const map={single:'СИНГЛ',ep:'EP',album:'АЛЬБОМ'};
  const cls=t==='single'?'single':t==='ep'?'ep':'album';
  return`<span class="type-badge ${cls}">${map[t]||t.toUpperCase()}</span>`;
}
function statusBadge(u){
  const now=Math.floor(Date.now()/1000);
  if(u.banned)return'<span class="badge banned-badge">ЗАБАНЕН</span>';
  if(u.role==='admin')return'<span class="badge admin">ADMIN</span>';
  if(u.sub_active&&(!u.sub_ends||u.sub_ends>now))return'<span class="badge sub">ПОДПИСКА</span>';
  const tl=u.trial_ends?Math.max(0,Math.ceil((u.trial_ends-now)/3600)):0;
  if(tl>0)return`<span class="badge trial">ТРИАЛ ${tl}ч</span>`;
  return'<span class="badge expired">ИСТЁК</span>';
}

// ── Artists ───────────────────────────────────────────────
async function loadArtists(){
  try{
    const[a,l]=await Promise.all([
      fetch('/api/artists').then(r=>r.json()),
      fetch('/library').then(r=>r.json()),
    ]);
    _artistsDB=a;_libData=l;
    const names=Object.keys(l),dbMap=Object.fromEntries(a.map(x=>[x.name,x]));
    let tot=0;
    for(const ar of Object.values(l))for(const al of Object.values(ar))tot+=al.tracks.length;
    document.getElementById('stat-artists').textContent=names.length;
    document.getElementById('stat-tracks').textContent=tot;
    const gs=['linear-gradient(135deg,#1e3a5f,#0a1a2e)','linear-gradient(135deg,#3d1f5c,#1a0a2e)','linear-gradient(135deg,#2a1200,#5c2a00)','linear-gradient(135deg,#003a2a,#001a12)','linear-gradient(135deg,#3a0a1e,#1a0010)'];
    document.getElementById('artist-grid').innerHTML=names.map((name,i)=>{
      const db=dbMap[name]||{},photo=db.photo||'';
      let tc=0;for(const al of Object.values(l[name]))tc+=al.tracks.length;
      return`<div class="artist-card" onclick="openArtistEdit(${JSON.stringify(name)})">
        <div class="artist-card-photo" style="background:${photo?'#000':gs[i%gs.length]}">
          ${photo?`<img src="${photo}" onerror="this.style.display='none'"/>`:`<span>${name[0]||'?'}</span>`}
          ${!photo?`<div class="no-photo-badge">НЕТ ФОТО</div>`:''}
        </div>
        <div class="artist-card-body">
          <div class="artist-card-name">${name}</div>
          <div class="artist-card-count">${Object.keys(l[name]).length} альб · ${tc} тр</div>
        </div>
      </div>`;
    }).join('');
  }catch(e){toast('Ошибка загрузки','error')}
}

// ── Artist Edit ───────────────────────────────────────────
let _artistImg = null; // HTMLImageElement
let _artistBW  = false;
let _artistPhotoFile = null; // File to upload

function openArtistEdit(name){
  _editingArtist = name;
  _artistImg = null; _artistBW = false; _artistPhotoFile = null;
  const db = _artistsDB.find(a=>a.name===name)||{};
  document.getElementById('artist-edit-title').textContent = name||'Новый артист';
  document.getElementById('artist-name').value = name||'';
  document.getElementById('artist-name').disabled = !!name;
  document.getElementById('artist-bio').value = db.bio||'';
  document.getElementById('artist-delete-btn').style.display = name?'':'none';
  document.getElementById('artist-photo-tools').style.display = 'none';
  document.getElementById('btn-bw').style.background = '';
  document.getElementById('btn-bw').style.color = '';
  // Clear file input
  document.getElementById('artist-photo-file').value = '';
  // Draw existing photo or placeholder
  if(db.photo){
    const img = new Image(); img.crossOrigin='anonymous';
    img.onload = ()=>{ _artistImg=img; drawArtistCanvas(); };
    img.onerror = ()=>{ clearCanvasToPlaceholder(); };
    img.src = db.photo;
    document.getElementById('artist-canvas-placeholder').style.opacity='0';
  } else {
    clearCanvasToPlaceholder();
  }
  document.getElementById('artist-overlay').classList.add('open');
}

function clearCanvasToPlaceholder(){
  const canvas = document.getElementById('artist-canvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0,0,160,160);
  document.getElementById('artist-canvas-placeholder').style.opacity='1';
  document.getElementById('artist-photo-tools').style.display='none';
  _artistImg = null; _artistPhotoFile = null;
}

function loadArtistPhoto(input){
  if(!input.files[0]) return;
  _artistPhotoFile = input.files[0];
  const url = URL.createObjectURL(_artistPhotoFile);
  const img = new Image();
  img.onload = ()=>{ _artistImg=img; drawArtistCanvas(); };
  img.src = url;
}

function drawArtistCanvas(){
  if(!_artistImg) return;
  const canvas = document.getElementById('artist-canvas');
  const ctx = canvas.getContext('2d');
  const s = 160;
  ctx.clearRect(0,0,s,s);
  // Circle clip
  ctx.save();
  ctx.beginPath(); ctx.arc(s/2,s/2,s/2,0,Math.PI*2); ctx.clip();
  // Draw image (cover fit)
  const r = Math.min(_artistImg.width,_artistImg.height);
  const sx = (_artistImg.width-r)/2, sy = (_artistImg.height-r)/2;
  ctx.drawImage(_artistImg, sx, sy, r, r, 0, 0, s, s);
  // B&W overlay
  if(_artistBW){
    const d = ctx.getImageData(0,0,s,s);
    for(let i=0;i<d.data.length;i+=4){
      const g = d.data[i]*0.299 + d.data[i+1]*0.587 + d.data[i+2]*0.114;
      d.data[i]=d.data[i+1]=d.data[i+2]=g;
    }
    ctx.putImageData(d,0,0);
  }
  ctx.restore();
  document.getElementById('artist-canvas-placeholder').style.opacity='0';
  document.getElementById('artist-photo-tools').style.display='flex';
}

function toggleBW(){
  _artistBW = !_artistBW;
  const btn = document.getElementById('btn-bw');
  btn.style.background = _artistBW ? 'var(--muted)' : '';
  btn.style.color = _artistBW ? 'var(--bg)' : '';
  drawArtistCanvas();
}

function clearArtistPhoto(){
  _artistBW = false;
  clearCanvasToPlaceholder();
}

function closeArtistEdit(e){
  if(e&&e.target!==document.getElementById('artist-overlay'))return;
  document.getElementById('artist-overlay').classList.remove('open');
}

async function saveArtist(){
  const name = _editingArtist || document.getElementById('artist-name').value.trim();
  if(!name) return toast('Введи имя','error');
  const bio = document.getElementById('artist-bio').value.trim();
  const fd = new FormData();
  fd.append('bio', bio);

  if(_artistImg){
    // Export canvas as blob
    const canvas = document.getElementById('artist-canvas');
    const blob = await new Promise(res=>canvas.toBlob(res,'image/jpeg',0.9));
    fd.append('photo_file', blob, (name.replace(/[^\w]/g,'_'))+'.jpg');
  }

  const res = await fetch(`/api/artists/${encodeURIComponent(name)}`,{method:'POST',body:fd});
  if(res.ok){
    toast(`${name} сохранён ✓`);
    document.getElementById('artist-overlay').classList.remove('open');
    loadArtists();
  } else toast('Ошибка сохранения','error');
}

async function deleteArtist(){
  if(!_editingArtist||!confirm(`Удалить ${_editingArtist}?`))return;
  await fetch(`/api/artists/${encodeURIComponent(_editingArtist)}`,{method:'DELETE'});
  toast('Удалён');document.getElementById('artist-overlay').classList.remove('open');loadArtists();
}

// ── Tracks admin ──────────────────────────────────────────
let _tracksFlat = []; // for search

async function loadTracksAdmin(){
  const data = await fetch('/api/library/admin').then(r=>r.json());
  _libData = data;
  _tracksFlat = [];
  // Build flat list for search
  for(const [artist,albums] of Object.entries(data)){
    for(const [album,info] of Object.entries(albums)){
      const aid = `${artist}/${album}`;
      for(const t of info.tracks) _tracksFlat.push({...t, album, artist, aid});
    }
  }
  renderTracksTree(data);
}

function renderTracksTree(data, openAlbums=new Set()){
  const tree = document.getElementById('tracks-tree');
  tree.innerHTML = Object.entries(data).map(([artist,albums])=>`
    <div style="margin-bottom:18px">
      <div style="font-family:'Unbounded',sans-serif;font-size:12px;font-weight:700;margin-bottom:8px;color:var(--gold)">${artist}</div>
      ${Object.entries(albums).map(([album,info])=>{
        const aid = `${artist}/${album}`;
        const aOn = info.enabled!==false;
        const typeLabel = info.type||'album';
        const isOpen = openAlbums.has(aid);
        return`<div class="album-block${isOpen?' open':''}" id="block-${CSS.escape(aid)}">
          <div class="album-hdr">
            <div class="album-hdr-info" style="cursor:pointer" onclick="toggleAlbumBlock('${escJ(aid)}')">
              <div class="album-hdr-name ${!aOn?'disabled-label':''}">${album}</div>
              <div class="album-hdr-meta">${typeBadge(typeLabel)} <span style="margin-left:4px;font-size:9px;color:var(--muted)">${info.artists||artist}</span></div>
            </div>
            <div class="album-hdr-actions">
              <button class="btn xs secondary" onclick="openAlbumEdit('${escJ(aid)}','${escJ(album)}','${escJ(artist)}')" title="Редактировать мета">✎</button>
              <div class="toggle ${aOn?'on':''}" onclick="toggleItem('${escJ(aid)}','album',${aOn},'${escJ(aid)}')" title="${aOn?'Выключить':'Включить'}"></div>
              <div class="album-hdr-chevron" onclick="toggleAlbumBlock('${escJ(aid)}')">
                <svg viewBox="0 0 24 24"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
              </div>
            </div>
          </div>
          <div class="album-tracks">
            ${info.tracks.map(t=>{
              const tOn = t.enabled!==false;
              return`<div class="track-row">
                <div class="track-row-name ${!tOn?'disabled-label':''}">${t.title}</div>
                ${!tOn?`<span style="font-size:9px;color:var(--red);margin-right:4px">ОТКЛ</span>`:''}
                <div class="toggle ${tOn?'on':''}" onclick="toggleItem('${escJ(t.id)}','track',${tOn},'${escJ(aid)}')"></div>
              </div>`;
            }).join('')}
          </div>
        </div>`;
      }).join('')}
    </div>`).join('');
}

function getOpenAlbums(){
  const open = new Set();
  document.querySelectorAll('.album-block.open').forEach(el=>{
    const id = el.id.replace(/^block-/,'');
    // CSS.escape adds escapes, need to find real id
    open.add(el.dataset.aid || el.id.slice(6));
  });
  // Better: store in dataset
  return open;
}

function toggleAlbumBlock(aid){
  const el = document.getElementById(`block-${CSS.escape(aid)}`);
  if(el) el.classList.toggle('open');
}

function toggleItem(id, type, currentlyOn, albumId){
  if(currentlyOn){
    _pendingDisable = {id, type, albumId};
    document.getElementById('reason-overlay').classList.add('open');
  } else {
    setTrackState(id, true, '', albumId);
  }
}
function closeReason(e){
  if(e&&e.target!==document.getElementById('reason-overlay'))return;
  document.getElementById('reason-overlay').classList.remove('open');
  _pendingDisable = null;
}
async function confirmDisable(){
  if(!_pendingDisable) return;
  const sel = document.getElementById('reason-select').value;
  const reason = sel==='custom' ? document.getElementById('reason-text').value : sel;
  const {id, albumId} = _pendingDisable;
  document.getElementById('reason-overlay').classList.remove('open');
  _pendingDisable = null;
  await setTrackState(id, false, reason, albumId);
}
async function setTrackState(id, enabled, reason, keepOpenAlbumId){
  const r = await fetch('/api/track-state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,enabled,reason})});
  if(r.ok){
    toast(enabled?'Включено ✓':'Отключено');
    // Сохраняем какие альбомы открыты
    const openSet = new Set();
    document.querySelectorAll('.album-block.open').forEach(el=>{
      // extract aid from element id
      openSet.add(decodeAlbumElId(el.id));
    });
    if(keepOpenAlbumId) openSet.add(keepOpenAlbumId);
    const data = await fetch('/api/library/admin').then(r=>r.json());
    _libData = data;
    renderTracksTree(data, openSet);
    // Re-apply search filter if active
    const q = document.getElementById('tracks-search')?.value;
    if(q) filterTracks(q);
  } else toast('Ошибка','error');
}

function decodeAlbumElId(elId){
  // el.id = "block-" + CSS.escape(aid), we need to recover aid
  // Simplest: find element and read data attribute
  const el = document.getElementById(elId);
  return el?.dataset?.aid || elId.replace(/^block-/,'');
}

// Attach data-aid to blocks after render
function attachAidData(){
  document.querySelectorAll('.album-block').forEach(el=>{
    if(!el.dataset.aid){
      // extract from id: "block-<escaped-aid>"
      // We'll set it properly from renderTracksTree
    }
  });
}

function filterTracks(q){
  q = q.toLowerCase().trim();
  if(!q){ renderTracksTree(_libData); return; }

  // Build filtered data structure preserving only matching
  const filtered = {};
  for(const [artist, albums] of Object.entries(_libData)){
    for(const [album, info] of Object.entries(albums)){
      const aid = `${artist}/${album}`;
      const artistMatch = artist.toLowerCase().includes(q);
      const albumMatch = album.toLowerCase().includes(q);
      const matchTracks = info.tracks.filter(t=>
        t.title.toLowerCase().includes(q) || artistMatch || albumMatch
      );
      if(matchTracks.length){
        if(!filtered[artist]) filtered[artist]={};
        filtered[artist][album] = {...info, tracks: matchTracks};
      }
    }
  }
  // Render filtered, all open
  const allIds = new Set();
  for(const [artist, albums] of Object.entries(filtered)){
    for(const album of Object.keys(albums)) allIds.add(`${artist}/${album}`);
  }
  renderTracksTree(filtered, allIds);
}

// ── Album Edit Sheet ──────────────────────────────────────
async function openAlbumEdit(aid, album, artist){
  _editingAlbumId = aid;
  document.getElementById('album-edit-title').textContent = album;
  document.getElementById('album-edit-sub').textContent = artist;
  // Load existing meta
  const meta = await fetch(`/api/album-meta/${encodeURIComponent(aid)}`).then(r=>r.json());
  document.getElementById('album-type').value = meta.type||'album';
  document.getElementById('album-year').value = meta.year||'';
  document.getElementById('album-artists').value = meta.artists||artist;
  // Cover: check meta then _libData
  const libCover = _libData[artist]?.[album]?.cover || '';
  const cover = meta.cover || libCover || '';
  if(cover){
    document.getElementById('album-cover-existing').style.display='block';
    document.getElementById('album-cover-existing-img').src = cover;
    document.getElementById('album-cover-upload').style.display='none';
  } else {
    document.getElementById('album-cover-existing').style.display='none';
    document.getElementById('album-cover-upload').style.display='block';
  }
  document.getElementById('album-cover-file').value='';
  document.getElementById('album-overlay').classList.add('open');
}
function closeAlbumEdit(e){
  if(e&&e.target!==document.getElementById('album-overlay'))return;
  document.getElementById('album-overlay').classList.remove('open');
}
function removeAlbumCover(){
  document.getElementById('album-cover-existing').style.display='none';
  document.getElementById('album-cover-upload').style.display='block';
}
function previewAlbumCoverFile(input){
  if(!input.files[0]) return;
  const url = URL.createObjectURL(input.files[0]);
  document.getElementById('album-cover-existing-img').src = url;
  document.getElementById('album-cover-existing').style.display='block';
  document.getElementById('album-cover-upload').style.display='none';
}
async function saveAlbumMeta(){
  if(!_editingAlbumId) return;
  const type    = document.getElementById('album-type').value;
  const year    = document.getElementById('album-year').value;
  const artists = document.getElementById('album-artists').value.trim();
  const file    = document.getElementById('album-cover-file').files[0];

  if(file){
    // Upload cover first
    const fd2 = new FormData();
    fd2.append('album_id', _editingAlbumId);
    fd2.append('cover', file);
    await fetch('/api/upload/cover',{method:'POST',body:fd2});
  }

  const res = await fetch(`/api/album-meta/${encodeURIComponent(_editingAlbumId)}`,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({type, year, artists})
  });
  if(res.ok){
    toast('Сохранено ✓');
    document.getElementById('album-overlay').classList.remove('open');
    loadTracksAdmin();
  } else toast('Ошибка','error');
}

// ── Music upload ──────────────────────────────────────────
function handleMusicDrop(e){
  e.preventDefault();
  document.getElementById('music-drop-zone').classList.remove('drag');
  uploadMusic(e.dataTransfer.files);
}
async function uploadMusic(files){
  const artist=document.getElementById('upload-artist').value.trim();
  const album=document.getElementById('upload-album').value.trim();
  const type=document.getElementById('upload-type').value;
  const year=document.getElementById('upload-year').value;
  const artists=document.getElementById('upload-artists').value.trim();
  if(!artist||!album)return toast('Введи артиста и альбом','error');
  if(!files.length)return;
  const fd=new FormData();
  fd.append('artist',artist);
  fd.append('album',album);
  fd.append('type',type);
  if(year)fd.append('year',year);
  if(artists)fd.append('artists',artists);
  for(const f of files)fd.append('files',f);
  const r=await fetch('/api/upload/music',{method:'POST',body:fd});
  if(r.ok){const d=await r.json();toast(`Загружено: ${d.saved.join(', ')}`);loadTracksAdmin()}
  else toast('Ошибка загрузки','error');
}

// ── Users ─────────────────────────────────────────────────
async function loadUsers(){
  _allUsers=await fetch('/api/users').then(r=>r.json());
  renderUsers(_allUsers);
}

function filterUsers(){
  const q=document.getElementById('users-search').value.toLowerCase();
  renderUsers(q?_allUsers.filter(u=>u.email.toLowerCase().includes(q)):_allUsers);
}

function renderUsers(users){
  if(!users.length){
    document.getElementById('users-list').innerHTML='<div class="empty">Нет пользователей</div>';
    return;
  }
  const now=Math.floor(Date.now()/1000);
  document.getElementById('users-list').innerHTML=users.map(u=>{
    const plays=u.play_count||0;
    const d=fmtDate(u.created_at);
    return`<div class="user-card ${u.banned?'banned-card':''}" onclick="openUserDetail(${u.id})">
      <div class="user-card-top">
        <div class="user-avatar">${u.email[0].toUpperCase()}</div>
        <div class="user-card-info">
          <div class="user-email">${u.email}</div>
          <div class="user-meta-row">
            ${statusBadge(u)}
            <span class="user-stat">📅 <strong>${d}</strong></span>
            <span class="user-stat">🎵 <strong>${plays}</strong></span>
          </div>
        </div>
        <svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:var(--muted);flex-shrink:0"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
      </div>
    </div>`;
  }).join('');
}

// ── User Detail ───────────────────────────────────────────
let _udUser = null;

async function openUserDetail(uid){
  _udUser = null;
  document.getElementById('user-overlay').classList.add('open');
  const u = await fetch(`/api/users/${uid}`).then(r=>r.json());
  _udUser = u;
  const now = Math.floor(Date.now()/1000);
  const subOk = u.sub_active && (!u.sub_ends || u.sub_ends > now);

  // Email
  document.getElementById('ud-email').textContent = u.email;

  // Badge
  let badge = statusBadge(u);
  document.getElementById('ud-badges').innerHTML = badge;

  // Stats
  document.getElementById('ud-plays').textContent = u.play_count ?? '—';
  document.getElementById('ud-created').textContent = fmtDate(u.created_at);

  // Sub text
  let subText = 'Нет подписки';
  if(subOk && u.sub_ends) subText = `Активна до ${fmtDate(u.sub_ends)}`;
  else if(subOk) subText = 'Активна (бессрочно)';
  else if(u.trial_ends && u.trial_ends > now){
    const h = Math.ceil((u.trial_ends - now)/3600);
    subText = `Триал: ${h}ч осталось`;
  }
  document.getElementById('ud-sub-text').textContent = subText;
  document.getElementById('ud-revoke-btn').style.display = subOk ? '' : 'none';

  // Role highlight
  const isUser = u.role === 'user';
  const ru = document.getElementById('ud-role-user');
  const ra = document.getElementById('ud-role-admin');
  ru.style.cssText = isUser ? 'background:var(--gold);color:#0c0a08' : '';
  ra.style.cssText = !isUser ? 'background:var(--gold);color:#0c0a08' : '';

  // Ban
  document.getElementById('ud-ban-reason').value = '';
  if(u.banned){
    document.getElementById('ud-ban-status').style.display = 'block';
    document.getElementById('ud-ban-status').textContent = `Забанен: ${u.ban_reason||'без причины'}`;
    document.getElementById('ud-unban-wrap').style.display = '';
  } else {
    document.getElementById('ud-ban-status').style.display = 'none';
    document.getElementById('ud-unban-wrap').style.display = 'none';
  }
}

function closeUserDetail(e){
  if(e && e.target !== document.getElementById('user-overlay')) return;
  document.getElementById('user-overlay').classList.remove('open');
  _udUser = null;
}

async function udGrant(days){
  if(!_udUser) return;
  const r = await fetch('/api/admin/grant',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:_udUser.id, days})});
  if(r.ok){ toast(`+${days} дней ✓`); loadUsers(); openUserDetail(_udUser.id); }
  else toast('Ошибка','error');
}

async function udRevoke(){
  if(!_udUser || !confirm('Отозвать подписку?')) return;
  const r = await fetch('/api/admin/grant',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:_udUser.id, revoke:true})});
  if(r.ok){ toast('Подписка отозвана'); loadUsers(); openUserDetail(_udUser.id); }
  else toast('Ошибка','error');
}

async function udSetRole(role){
  if(!_udUser) return;
  const r = await fetch(`/api/users/${_udUser.id}`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'role', role})});
  if(r.ok){ toast(`Роль: ${role} ✓`); loadUsers(); openUserDetail(_udUser.id); }
  else toast('Ошибка','error');
}

async function udBan(ban_type){
  if(!_udUser) return;
  const reason = document.getElementById('ud-ban-reason').value.trim();
  const r = await fetch(`/api/users/${_udUser.id}`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'ban', ban_type, reason})});
  if(r.ok){ toast('Забанен'); loadUsers(); openUserDetail(_udUser.id); }
  else toast('Ошибка','error');
}

async function udUnban(){
  if(!_udUser) return;
  const r = await fetch(`/api/users/${_udUser.id}`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'unban'})});
  if(r.ok){ toast('Разбанен ✓'); loadUsers(); openUserDetail(_udUser.id); }
  else toast('Ошибка','error');
}


// ── Init ──────────────────────────────────────────────────
loadArtists();
