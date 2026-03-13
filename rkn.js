/**
 * rkn.js — плагин для Tape
 * Подключает треки с твоего сервера
 *
 * Как использовать:
 * 1. Положи mp3 файлы рядом с этим файлом
 * 2. Отредактируй массив tracks ниже
 * 3. Залей на GitHub / свой сервер
 * 4. В приложении Tape → Плагины → вставь ссылку на этот файл
 */

(function() {

  // ══════════════════════════════════════════
  //  НАСТРОЙКИ — меняй только здесь
  // ══════════════════════════════════════════

  // Базовый URL откуда берётся музыка
  // Пример для ngrok: 'https://abc123.ngrok-free.app'
  // Пример для GitHub raw: 'https://raw.githubusercontent.com/USERNAME/REPO/main'
  const BASE_URL = 'https://ТВОЙ_URL_СЮДА';

  // Список треков
  // url    — путь к mp3 файлу (относительно BASE_URL)
  // cover  — путь к обложке jpg/png (или убери поле — покажется эмодзи)
  // emoji  — показывается если нет обложки
  const tracks = [

    {
      title:  'Название трека 1',
      artist: 'Артист',
      url:    BASE_URL + '/tracks/track1.mp3',
      cover:  BASE_URL + '/covers/track1.jpg',
      duration: '3:42',
      emoji:  '🎵',
    },

    {
      title:  'Название трека 2',
      artist: 'Артист',
      url:    BASE_URL + '/tracks/track2.mp3',
      cover:  BASE_URL + '/covers/track2.jpg',
      duration: '4:10',
      emoji:  '🎶',
    },

    {
      title:  'Название трека 3',
      artist: 'Артист',
      url:    BASE_URL + '/tracks/track3.mp3',
      duration: '3:55',
      emoji:  '🔥',
    },

  ];

  // ══════════════════════════════════════════
  //  РЕГИСТРАЦИЯ ПЛАГИНА — не трогай
  // ══════════════════════════════════════════

  window.TapePlugin.register({
    id:      'rkn',
    name:    'RKN',
    version: '1.0.0',
    desc:    'Треки без цензуры',
    emoji:   '📻',
    color:   'rgba(212,168,64,0.15)',
    enabled: true,
    tracks:  tracks,
  });

  console.log('[RKN plugin] загружено треков:', tracks.length);

})();
