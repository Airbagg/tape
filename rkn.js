(function() {
  const BASE = 'https://490d-109-122-201-121.ngrok-free.app/tracks';

  const tracks = [
    { title: 'Вязки',                  artist: 'Баста & Гуф', url: BASE + '/vyazki.mp3' },
    { title: 'Другая волна',           artist: 'Баста & Гуф', url: BASE + '/drugaya_volna.mp3' },
    { title: 'Если бы',                artist: 'Баста & Гуф', url: BASE + '/esli_by_.mp3' },
    { title: 'Заколоченное',           artist: 'Баста & Гуф', url: BASE + '/zakolochennoe.mp3' },
    { title: 'Зеркало',                artist: 'Баста & Гуф', url: BASE + '/zerkalo.mp3' },
    { title: 'Как есть',               artist: 'Баста & Гуф', url: BASE + '/kak_est.mp3' },
    { title: 'Китай',                  artist: 'Баста & Гуф', url: BASE + '/kitai_.mp3' },
    { title: 'Личное дело',            artist: 'Баста & Гуф', url: BASE + '/lichnoe_delo.mp3' },
    { title: 'Не все потеряно пока',   artist: 'Баста & Гуф', url: BASE + '/ne_vse_poteryano_poka.mp3' },
    { title: 'Самурай',                artist: 'Баста & Гуф', url: BASE + '/samurai_.mp3' },
    { title: 'Соответственно',         artist: 'Баста & Гуф', url: BASE + '/sootvetstvenno.mp3' },
    { title: 'Только сегодня',         artist: 'Баста & Гуф', url: BASE + '/tolko_segodnya.mp3' },
    { title: 'Ходим по краю',          artist: 'Баста & Гуф', url: BASE + '/hodim_po_krayu.mp3' },
    { title: 'ЧП',                     artist: 'Баста & Гуф', url: BASE + '/chp.mp3' },
  ];

  window.TapePlugin.register({
    id:      'rkn',
    name:    'Баста & Гуф',
    version: '1.0.0',
    desc:    'Альбом без цензуры',
    emoji:   '🎤',
    color:   'rgba(212,168,64,0.15)',
    enabled: true,
    tracks:  tracks,
  });

  console.log('[RKN] загружено треков:', tracks.length);
})();
