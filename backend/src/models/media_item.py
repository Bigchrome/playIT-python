import peewee
import requests
import logging
from peewee import *
from src.utils.auth import Auth
from src.models.base import BaseModel

YOUTUBE = "youtube"
SPOTIFY = "spotify"
SOUNDCLOUD = "soundcloud"

VOTE_LIMIT = -2
DURATION_LIMIT_MAP = {
    YOUTUBE: 60*60*3, # 3 hour
    SPOTIFY: 60*60, # 1 hour
    SOUNDCLOUD: 60*60, # 1 hour
}

SOUNDCLOUD_ID = "a2cfca0784004b38b85829ba183327cb"

URL_MAP = {
    YOUTUBE: "http://gdata.youtube.com/feeds/api/videos/%s?alt=json",
    SPOTIFY: "http://ws.spotify.com/lookup/1/.json?uri=spotify:track:%s",
    SOUNDCLOUD: "http://api.soundcloud.com/tracks/%s.json?client_id=" + SOUNDCLOUD_ID
}

class MediaItemError(Exception):
    pass


class MediaItem(BaseModel):

    title = CharField(default="")
    author = CharField(default="")
    description = CharField(default="")
    thumbnail = CharField(default="")
    cid = CharField()
    nick = CharField()
    type = CharField()
    external_id = CharField()
    duration = IntegerField()
    album = CharField(null=True)

    def exists(self):
        return MediaItem.fetch().where(
            MediaItem.external_id == self.external_id &
            MediaItem.type == self.type
        ).first() is not None

    def save(self, *args, **kwargs):
        if self.exists():
            raise MediaItemError("Item already exists")

        allowed_duration = DURATION_LIMIT_MAP.get(self.type)
        if self.duration > allowed_duration:
            raise MediaItemError("duration %d is longer then allowed %d" % (self.duration, allowed_duration))

        super(MediaItem, self).save(*args, **kwargs)

    def check_value(self):
        from src.models.vote import Vote
        votes = Vote.fetch(
            fn.Sum(Vote.value).alias("value")
        ).where(Vote.item == self).first()

        if votes and float(votes.value) <= VOTE_LIMIT:
            Vote.delete(permanently=True).where(Vote.item == self).execute()
            self.delete_instance()

    @staticmethod
    def create_media_item(cid, media_type, external_id):
        creator = getattr(MediaItem, "create_" + media_type + "_item")
        item = MediaItem()
        item.external_id = external_id
        item.type = media_type

        if item.exists():
            raise MediaItemError("Item already exists")

        url = URL_MAP.get(media_type) % external_id
        response = requests.get(url)
        data = response.json()

        item = creator(item, data)
        user = Auth.get_user(cid)
        item.cid = cid
        if user:
            item.nick = user.get("nick", "")

        return item

    @staticmethod
    def create_youtube_item(item, data):

        data = data.get("entry")

        item.title = data.get("title").get("$t")
        item.author = data.get("author")[0].get("name").get("$t")
        item.description = data.get("content").get("$t")
        item.thumbnail = "http://i.ytimg.com/vi/%s/mqdefault.jpg" % item.external_id

        try:
            item.duration = int(data.get("media$group").get("yt$duration").get("seconds"))
        except(ValueError, TypeError):
            item.duration = 1337

        return item

    @staticmethod
    def create_spotify_item(item, data):

        data = data.get("track")

        item.title = data.get("name")
        item.artists = ", ".join((a.get("name") for a in data.get("artists")))
        item.album = data.get("album").get("name")
        try:
            item.duration = int(data.get("duration") + 0.5)
        except (TypeError, ValueError) as e:
            logging.error("Failed to get duration for spotify item")
            item.duration = 1337

        thumbnail_url = "https://embed.spotify.com/oembed/?url=spotify:track:%s" % item.external_id
        thumbnail_resp = requests.get(thumbnail_url)
        thumbnail_data = thumbnail_resp.json()

        item.thumbnail = thumbnail_data.get("thumbnail_url")

        return item

    @staticmethod
    def create_soundcloud_item(item, data):

        item.title = data.get("title")
        item.author = data.get("user").get("username")
        item.thumbnail = data.get("artwork_url")
        item.duration = int(data.get("duration")/1000 + 0.5)

        return item

    @staticmethod
    def valid_user(cid):
        # TODO, proper check
        return isinstance(cid, str) and len(cid) > 0

    @staticmethod
    def get_queue():
        from src.models.vote import Vote
        return MediaItem.fetch(
            MediaItem, fn.Sum(Vote.value).alias("value")
        ).join(Vote).group_by(MediaItem.external_id).order_by(fn.Sum(Vote.value).desc(), MediaItem.created_at)

