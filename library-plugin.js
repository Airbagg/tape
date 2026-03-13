// tape — library plugin (автосканирование /library)
(async () => {
  try {
    const res = await fetch('/library');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    // Новый формат: {artist: {album: {tracks:[], cover, enabled}}}
    const tracks = [];
    // Кэшируем фото артистов из API
    const artistPhotos = {};

    for (const [artist, albums] of Object.entries(data)) {
      // Подтягиваем фото артиста из БД
      try {
        const ar = await fetch(`/api/artists/${encodeURIComponent(artist)}`).then(r=>r.json());
        if (ar.photo) artistPhotos[artist] = ar.photo;
      } catch(e) {}

      for (const [album, info] of Object.entries(albums)) {
        // info может быть массивом (старый формат) или объектом {tracks, cover, enabled}
        const albumTracks = Array.isArray(info) ? info : (info.tracks || []);
        for (const t of albumTracks) {
          tracks.push(t);
        }
      }
    }

    // Сохраняем фото в localStorage для рендера
    const stored = JSON.parse(localStorage.getItem('tape_artist_photos') || '{}');
    Object.assign(stored, artistPhotos);
    localStorage.setItem('tape_artist_photos', JSON.stringify(stored));

    if (tracks.length > 0) {
      window.TapePlugin.register({
        name: 'Библиотека',
        desc: 'Локальная библиотека · ' + tracks.length + ' треков',
        emoji: '💿',
        tracks,
      });
    } else {
      console.log('[Library] Треков не найдено');
    }
  } catch(e) {
    console.warn('[Library] Ошибка загрузки:', e.message);
  }
})();
