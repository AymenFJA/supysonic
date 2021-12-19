# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2020 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

from __future__ import unicode_literals

import argparse
import threading as mt
import subprocess as sp

from os.path import expanduser

from flask import request
from pony.orm import select
from datetime import datetime

from . import api_routing
from collections import OrderedDict

from ..db import Folder, Track, Artist, Album
from .exceptions import MissingParameter

from supysonic import ytmdl


def scan_and_update_DB():

    sp.run(['supysonic-cli folder scan'], shell =True)

def download_song(query):
    try:

        import youtube_dl
        from ytmusicapi import YTMusic

    except ImportError as error:
        raise ImportError(error)
    
    try:

        ytmusic = YTMusic('')
        search_results = ytmusic.search(query= str(query),
                                        filter= 'songs')[0]
        song_id = search_results['videoId']
        song_title = search_results['title']
        song_url = "https://music.youtube.com/watch?v={0}".format(song_id)

        args = argparse.Namespace(SONG_NAME=song_title.split(' '),
                                    album=None, artist=None, ask_meta_name=False,
                                    choice=1, disable_file=False,
                                    disable_metaadd=False, disable_sort=False,
                                    download_archive=None, format='mp3',
                                    get_opts=False, ignore_chapters=False,
                                    ignore_errors=False, itunes_id=None,
                                    keep_chapter_name=False, level='INFO',
                                    list=None, list_level=False, manual_meta=False,
                                    nolocal=False, on_meta_error=None, 
                                    output_dir='/home/aymenalsaadi/Music/',
                                    pl_end=None, pl_items=None, pl_start=None, proxy=None,
                                    quiet=True, skip_meta=False, song=None, spotify_id=None,
                                    title_as_name=False, trim=False, url=song_url)

        ytmdl.main(args)
        scan_and_update_DB()

        return True

    except Exception as error:
        raise Exception(error)

@api_routing("/search")
def old_search():
    artist, album, title, anyf, count, offset, newer_than = map(
        request.values.get,
        ("artist", "album", "title", "any", "count", "offset", "newerThan"),
    )

    count = int(count) if count else 20
    offset = int(offset) if offset else 0
    newer_than = int(newer_than) / 1000 if newer_than else 0
    min_date = datetime.fromtimestamp(newer_than)

    if artist:
        query = select(
            t.folder.parent
            for t in Track
            if artist in t.folder.parent.name and t.folder.parent.created > min_date
        )
    elif album:
        query = select(
            t.folder
            for t in Track
            if album in t.folder.name and t.folder.created > min_date
        )
    elif title:
        query = Track.select(lambda t: title in t.title and t.created > min_date)
    elif anyf:
        folders = Folder.select(lambda f: anyf in f.name and f.created > min_date)
        tracks = Track.select(lambda t: anyf in t.title and t.created > min_date)
        res = folders[offset : offset + count]
        fcount = folders.count()
        if offset + count > fcount:
            toff = max(0, offset - fcount)
            tend = offset + count - fcount
            res = res[:] + tracks[toff:tend][:]

        return request.formatter(
            "searchResult",
            {
                "totalHits": folders.count() + tracks.count(),
                "offset": offset,
                "match": [
                    r.as_subsonic_child(request.user)
                    if isinstance(r, Folder)
                    else r.as_subsonic_child(request.user, request.client)
                    for r in res
                ],
            },
        )
    else:
        raise MissingParameter("search")

    return request.formatter(
        "searchResult",
        {
            "totalHits": query.count(),
            "offset": offset,
            "match": [
                r.as_subsonic_child(request.user)
                if isinstance(r, Folder)
                else r.as_subsonic_child(request.user, request.client)
                for r in query[offset : offset + count]
            ],
        },
    )


@api_routing("/search2")
def new_search():
    query = request.values["query"]
    (
        artist_count,
        artist_offset,
        album_count,
        album_offset,
        song_count,
        song_offset,
    ) = map(
        request.values.get,
        (
            "artistCount",
            "artistOffset",
            "albumCount",
            "albumOffset",
            "songCount",
            "songOffset",
        ),
    )

    artist_count = int(artist_count) if artist_count else 20
    artist_offset = int(artist_offset) if artist_offset else 0
    album_count = int(album_count) if album_count else 20
    album_offset = int(album_offset) if album_offset else 0
    song_count = int(song_count) if song_count else 20
    song_offset = int(song_offset) if song_offset else 0

    artists = select(
        t.folder.parent for t in Track if query in t.folder.parent.name
    ).limit(artist_count, artist_offset)
    albums = select(t.folder for t in Track if query in t.folder.name).limit(
        album_count, album_offset
    )
    songs = Track.select(lambda t: query in t.title).limit(song_count, song_offset)

    if not songs:
        
        dw_song = mt.Thread(target=download_song , args=(query,))
        #dw_song.daemon = True
        dw_song.start()
        return request.formatter("searchResult2", 'Not found in the DB, downloading....')

    else:
            
        return request.formatter(
            "searchResult2",
            OrderedDict(
                (
                    ("artist", [a.as_subsonic_artist(request.user) for a in artists]),
                    ("album", [f.as_subsonic_child(request.user) for f in albums]),
                    (
                        "song",
                        [t.as_subsonic_child(request.user, request.client) for t in songs],
                    ),
                )
            ),
        )


@api_routing("/search3")
def search_id3():
    query = request.values["query"]
    (
        artist_count,
        artist_offset,
        album_count,
        album_offset,
        song_count,
        song_offset,
    ) = map(
        request.values.get,
        (
            "artistCount",
            "artistOffset",
            "albumCount",
            "albumOffset",
            "songCount",
            "songOffset",
        ),
    )

    artist_count = int(artist_count) if artist_count else 20
    artist_offset = int(artist_offset) if artist_offset else 0
    album_count = int(album_count) if album_count else 20
    album_offset = int(album_offset) if album_offset else 0
    song_count = int(song_count) if song_count else 20
    song_offset = int(song_offset) if song_offset else 0

    artists = Artist.select(lambda a: query in a.name).limit(
        artist_count, artist_offset
    )
    albums = Album.select(lambda a: query in a.name).limit(album_count, album_offset)
    songs = Track.select(lambda t: query in t.title).limit(song_count, song_offset)

    return request.formatter(
        "searchResult3",
        OrderedDict(
            (
                ("artist", [a.as_subsonic_artist(request.user) for a in artists]),
                ("album", [a.as_subsonic_album(request.user) for a in albums]),
                (
                    "song",
                    [t.as_subsonic_child(request.user, request.client) for t in songs],
                ),
            )
        ),
    )
