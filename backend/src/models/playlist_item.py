# https://gdata.youtube.com/feeds/api/playlists/PLUcJ_HmO2bE8ohOVEGmN7WkrVhWFui0c4?v=2&alt=json

import peewee
import requests
import logging
from peewee import *
from src.utils.auth import Auth
from src.models.base import BaseModel
from src.models.media_item import MediaItem

YOUTUBE_LIST = "youtube_list"
SPOTIFY_LIST = "spotify_list"

VOTE_LIMIT = -2

URL_MAP = {
    YOUTUBE_LIST: "https://gdata.youtube.com/feeds/api/playlists/%s?v=2&alt=json",
    SPOTIFY_LIST: "",  # Spotify requires api key and authorization
}


class PlaylistItemError(Exception):
    pass


class PlaylistItem(BaseModel):

    title = CharField(default="")
    author = CharField(default="")
    description = CharField(default="")
    thumbnail = CharField(default="")
    cid = CharField()
    nick = CharField()
    type = CharField()
    external_id = CharField()

    def exists(self):
        return PlaylistItem.fetch().where(
            PlaylistItem.external_id == self.external_id,
            PlaylistItem.type == self.type
        ).exists()

    def _get_votes(self):
        from src.models.vote import Vote
        vote = Vote.fetch(
            fn.Sum(Vote.value).alias("value")
        ).where(Vote.item == self).first()

        return vote

    def check_value(self):
        from src.models.vote import PlaylistVote
        votes = self._get_votes()

        if votes and float(votes.value) <= VOTE_LIMIT:
            PlaylistVote.delete(permanently=True).where(PlaylistVote.item == self).execute()
            self.delete_instance()

    def value(self):
        vote = self._get_votes()
        if vote:
            return float(vote.value)
        else:
            return 0.0

    def with_value(self):
        from src.models.vote import PlaylistVote
        query = PlaylistItem.fetch(
            PlaylistItem, fn.Sum(PlaylistVote.value).alias("value")
        ).where(
            PlaylistItem.id == self.id
        ).join(PlaylistVote).group_by(PlaylistItem.external_id).order_by(fn.Sum(PlaylistVote.value).desc())

        item = query.first()
        item_dict = item.get_dictionary()
        item_dict["value"] = item.value

        return item_dict

    def delete_instance(self, permanently=False, recursive=False, delete_nullable=False):
        from src.models.vote import PlaylistVote
        PlaylistVote.delete(permanently=True).where(PlaylistVote.item == self.id).execute()

        return super(PlaylistItem, self).delete_instance(permanently, recursive, delete_nullable)

    @staticmethod
    def get_item(media_type, external_id):
        return PlaylistItem.fetch().where(
            (PlaylistItem.external_id == external_id) &
            (PlaylistItem.type == media_type)
        ).first()

    @staticmethod
    def create_media_item(cid, media_type, external_id):
        creator = getattr(PlaylistItem, "create_" + media_type + "_item")
        item = PlaylistItem()
        item.external_id = external_id
        item.type = media_type

        if item.exists():
            raise PlaylistItemError("Item already exists")

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
    def create_youtube_list_item(item, data):

        data = data.get("feed")

        item.title = data.get("title").get("$t")
        item.author = data.get("author")[0].get("name").get("$t")

        item.thumbnail = data.get("media$group").get("media$thumbnail")[1].get("url")

        return item

    @staticmethod
    def create_spotify_list_item(item, data):
        pass

    @staticmethod
    def valid_user(cid):
        # TODO, proper check
        return isinstance(cid, str) and len(cid) > 0

    @staticmethod
    def get_queue():
        from src.models.vote import PlaylistVote
        return PlaylistItem.fetch(
            PlaylistItem, fn.Sum(PlaylistVote.value).alias("value")
        ).join(PlaylistVote).group_by(PlaylistItem.external_id).order_by(fn.Sum(PlaylistVote.value).desc(), PlaylistItem.created_at)

    @staticmethod
    def get_index(playlist, index):
        media_type = playlist.type
        external_id = playlist.external_id
        url = URL_MAP.get(media_type) % external_id
        response = requests.get(url)
        data = response.json()

        retriever = getattr(PlaylistItem, "get_index_" + media_type)

        return retriever(data, index)

    @staticmethod
    def get_index_youtube_list(data, index):
        data = data.get("feed")
        items = data.get("entry")
        amount = len(items)

        index = index % amount

        item = items[index]

        item = MediaItem.parse_youtube_entry(MediaItem(), item)

        return item







