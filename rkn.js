(async () => {
  try {
    const BASE = 'https://citizenship-inquiry-vbulletin-worcester.trycloudflare.com';
    const res = await fetch(BASE + '/library');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    const tracks = [];

    for (const [artist, albums] of Object.entries(data)) {
      if (!albums || typeof albums !== 'object') continue;

      for (const [album, info] of Object.entries(albums)) {
        if (!info || typeof info !== 'object') continue;

        const albumTracks = Array.isArray(info) ? info : (info.tracks || []);
        const cover = Array.isArray(info) ? null : (info.cover || null);

        for (const t of albumTracks) {
          tracks.push({...t, cover: t.cover || cover});
        }
      }
    }

    if (tracks.length > 0) {
      window.TapePlugin.register({
        name: 'RKN',
        desc: 'Музыка без цензуры · ' + tracks.length + ' треков',
        emoji: '📻',
        tracks,
      });
      console.log('[RKN] загружено треков:', tracks.length);
    } else {
      console.warn('[RKN] Треков не найдено');
    }
  } catch(e) {
    console.warn('[RKN] Ошибка загрузки:', e.message);
  }
})();
