(function() {
  // Адрес твоего сервера (ngrok или localhost)
  const BASE = 'https://490d-109-122-201-121.ngrok-free.app';

  async function load() {
    try {
      const res = await fetch(BASE + '/library');
      const library = await res.json();
      // library = { "Артист": { "Альбом": [ {title,artist,album,url,cover}, ... ] } }

      const allTracks = [];
      for (const artist of Object.keys(library)) {
        for (const album of Object.keys(library[artist])) {
          for (const track of library[artist][album]) {
            // url уже относительный (/tracks/...) — делаем абсолютным
            allTracks.push({
              ...track,
              url:   track.url.startsWith('http') ? track.url : BASE + track.url,
              cover: track.cover
                ? (track.cover.startsWith('http') ? track.cover : BASE + track.cover)
                : null,
            });
          }
        }
      }

      // Убираем дубли (совместные артисты дублируются в library)
      const seen = new Set();
      const unique = allTracks.filter(t => {
        const key = t.url;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

      window.TapePlugin.register({
        id:      'local-library',
        name:    'Моя библиотека',
        version: '1.0.0',
        desc:    `Загружено ${unique.length} треков`,
        emoji:   '🎵',
        color:   'rgba(212,168,64,0.15)',
        enabled: true,
        tracks:  unique,
      });

      console.log('[Library] загружено треков:', unique.length);
    } catch(e) {
      console.error('[Library] ошибка загрузки:', e);
    }
  }

  load();
})();
