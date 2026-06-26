/**
 * Хелперы для работы с каталогом аудио-треков.
 *
 * Переэкспортирует функции из src/data/audio.ts единым API.
 * Если в будущем каталог переедет в JSON+getStaticPaths-паттерн
 * (как src/lib/experts.ts), достаточно будет изменить только этот файл.
 */

export type { AudioTrack } from '../data/audio';
export { getAllTracks, getPublicTracks, getLockedTracks, getTrackBySlug } from '../data/audio';
