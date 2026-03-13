(function() {
  const BASE = 'https://490d-109-122-201-121.ngrok-free.app/tracks';
  const ALBUM = 'Баста х Гуф';
  const COVER = BASE + '/../cover.jpg'; // положи cover.jpg в папку tape/

  const tracks = [
    { title: 'Вязки',                artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/vyazki.mp3',           cover: COVER },
    { title: 'Другая волна',         artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/drugaya_volna.mp3',    cover: COVER },
    { title: 'Если бы',              artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/esli_by_.mp3',         cover: COVER },
    { title: 'Заколоченное',         artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/zakolochennoe.mp3',    cover: COVER },
    { title: 'Зеркало',              artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/zerkalo.mp3',          cover: COVER },
    { title: 'Как есть',             artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/kak_est.mp3',          cover: COVER },
    { title: 'Китай',                artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/kitai_.mp3',           cover: COVER },
    { title: 'Личное дело',          artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/lichnoe_delo.mp3',     cover: COVER },
    { title: 'Не все потеряно пока', artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/ne_vse_poteryano_poka.mp3', cover: COVER },
    { title: 'Самурай',              artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/samurai_.mp3',         cover: COVER },
    { title: 'Соответственно',       artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/sootvetstvenno.mp3',  cover: COVER },
    { title: 'Только сегодня',       artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/tolko_segodnya.mp3',  cover: COVER },
    { title: 'Ходим по краю',        artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/hodim_po_krayu.mp3',  cover: COVER },
    { title: 'ЧП',                   artist: 'Баста & Гуф', album: ALBUM, url: BASE + '/chp.mp3',              cover: COVER },
  ];

  window.TapePlugin.register({
    id:      'rkn',
    name:    'Баста х Гуф',
    version: '1.0.0',
    desc:    'Альбом без цензуры',
    emoji:   '🎤',
    color:   'rgba(212,168,64,0.15)',
    enabled: true,
    tracks:  tracks,
  });

  console.log('[RKN] загружено треков:', tracks.length);
})();
