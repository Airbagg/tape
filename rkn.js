(function() {
  const BASE   = 'https://490d-109-122-201-121.ngrok-free.app';
  const TRACKS = BASE + '/tracks/%D0%91%D0%B0%D1%81%D1%82%D0%B0/%D0%91%D0%B0%D1%81%D1%82%D0%B0%20%D1%85%20%D0%93%D1%83%D1%84';
  const COVER  = TRACKS + '/cover.jpg';

  const tracks = [
    { title: 'Вязки',                artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/vyazki.mp3',                cover: COVER },
    { title: 'Другая волна',         artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/drugaya_volna.mp3',         cover: COVER },
    { title: 'Если бы',              artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/esli_by_.mp3',              cover: COVER },
    { title: 'Заколоченное',         artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/zakolochennoe.mp3',         cover: COVER },
    { title: 'Зеркало',              artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/zerkalo.mp3',               cover: COVER },
    { title: 'Как есть',             artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/kak_est.mp3',               cover: COVER },
    { title: 'Китай',                artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/kitai_.mp3',                cover: COVER },
    { title: 'Личное дело',          artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/lichnoe_delo.mp3',          cover: COVER },
    { title: 'Не все потеряно пока', artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/ne_vse_poteryano_poka.mp3', cover: COVER },
    { title: 'Самурай',              artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/samurai_.mp3',              cover: COVER },
    { title: 'Соответственно',       artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/sootvetstvenno.mp3',        cover: COVER },
    { title: 'Только сегодня',       artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/tolko_segodnya.mp3',        cover: COVER },
    { title: 'Ходим по краю',        artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/hodim_po_krayu.mp3',        cover: COVER },
    { title: 'ЧП',                   artist: 'Баста & Гуф', album: 'Баста х Гуф', url: TRACKS + '/chp.mp3',                   cover: COVER },
  ];

  window.TapePlugin.register({
    id:      'rkn',
    name:    'Баста х Гуф',
    version: '1.2.0',
    desc:    'Альбом без цензуры',
    emoji:   '🎤',
    color:   'rgba(212,168,64,0.15)',
    enabled: true,
    tracks:  tracks,
  });

  console.log('[RKN] загружено треков:', tracks.length);
})();
