from metadata_utils.CF_Program import get_all_mp3_as_obj

LIVE_ARCHIVE_PATH = r'C:\Users\Nyss\Downloads\Neuro Karaoke Archive'

for song in get_all_mp3_as_obj(LIVE_ARCHIVE_PATH):
    if song.xxHash:
        song.set_album_image()
        song.save()

