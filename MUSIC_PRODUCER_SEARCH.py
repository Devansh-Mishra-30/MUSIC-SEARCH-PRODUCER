#!/usr/bin/env python3
import os
import time
import csv
import argparse
import requests

API_BASE = "https://api.genius.com"

def request_genius(path, token, params=None):
    """Helper to make a GET request to the Genius API."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}{path}", headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

def find_producer_id(name, token):
    """Search Genius for the producer name and return the first matching artist ID."""
    data = request_genius("/search", token, params={"q": name})
    for hit in data["response"]["hits"]:
        artist = hit["result"]["primary_artist"]
        if name.lower() in artist["name"].lower():
            return artist["id"], artist["name"]
    raise ValueError(f"No producer artist found for '{name}'")

def fetch_all_songs_for_artist(artist_id, token):
    """Paginate through /artists/{id}/songs to collect all song IDs."""
    page = 1
    all_songs = []
    while True:
        data = request_genius(f"/artists/{artist_id}/songs", token,
                              params={"per_page": 50, "page": page})
        songs = data["response"]["songs"]
        if not songs:
            break
        all_songs.extend(songs)
        page += 1
        time.sleep(0.5)  # be nice to the API
    return all_songs

def filter_songs_by_producer(song_list, producer_id, token):
    """For each song ID, fetch details and keep only those produced by producer_id."""
    filtered = []
    for s in song_list:
        sid = s["id"]
        detail = request_genius(f"/songs/{sid}", token)["response"]["song"]
        # extract producer_artists
        producers = [p["name"] for p in detail.get("producer_artists", [])]
        producer_ids = [p["id"] for p in detail.get("producer_artists", [])]
        if producer_id in producer_ids:
            filtered.append({
                "song_id": sid,
                "title": detail["title"],
                "primary_artist": detail["primary_artist"]["name"],
                "producers": "; ".join(producers),
                "release_date": detail.get("release_date") or "",
                "url": detail["url"]
            })
        time.sleep(0.2)
    return filtered

def save_to_csv(records, path):
    """Write list of dicts to a CSV file."""
    if not records:
        print("No records to write.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

def main():
    p = argparse.ArgumentParser(
        description="Fetch all songs produced by a Genius producer and save to CSV"
    )
    p.add_argument("producer", help="Producer name to search for")
    p.add_argument("--token", help="Genius API token",
                   default=os.getenv("GENIUS_ACCESS_TOKEN"))
    p.add_argument("--output", help="Output CSV filename",
                   default="songs_by_producer.csv")
    args = p.parse_args()

    if not args.token:
        p.error("A Genius API token must be provided via --token or GENIUS_ACCESS_TOKEN.")

    print(f"Looking up producer '{args.producer}'…")
    pid, pname = find_producer_id(args.producer, args.token)
    print(f"Found producer ID {pid} ({pname}). Fetching song list…")

    all_songs = fetch_all_songs_for_artist(pid, args.token)
    print(f"Got {len(all_songs)} total songs associated with artist ID {pid}.")
    
    print("Filtering songs where this artist is credited as producer…")
    produced = filter_songs_by_producer(all_songs, pid, args.token)
    print(f"{len(produced)} songs found where '{pname}' is a producer.")

    print(f"Writing to '{args.output}'…")
    save_to_csv(produced, args.output)
    print("Done.")

if __name__ == "__main__":
    main()
