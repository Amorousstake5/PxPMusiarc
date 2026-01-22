import requests
import json
import pygame
import os
import tempfile
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from urllib.parse import quote

# Initialize pygame mixer
try:
    pygame.mixer.init()
except Exception as e:
    print(f"pygame mixer init failed: {e}")

class ArchiveMusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hybrid Music Player - Archive.org + Local")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        self.current_playlist = []  # Hybrid: list of dicts {'name':, 'type': 'local'/'remote', 'path' or 'url':}
        self.current_track_index = -1
        self.is_playing = False
        self.temp_audio_file = None
        self.temp_image_file = None
        self.photo_image = None
        self.albums_data = []
        self.download_dir = "./downloads"  # Default local music directory
        os.makedirs(self.download_dir, exist_ok=True)

        self.create_widgets()
        self._setup_window_close_handler()

    def _setup_window_close_handler(self):
        """Ensure music stops when window is closed"""
        def on_closing():
            self.stop_playback()
            try:
                pygame.mixer.quit()     # Explicitly shut down mixer
            except:
                pass
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)

    def create_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill="both", expand=True)

        # Left: Artwork
        left_frame = ttk.Frame(main_pane, padding=12)
        main_pane.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Album Artwork", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.artwork_label = ttk.Label(left_frame, text="[No artwork]", relief="sunken",
                                       width=28, anchor="center", background="#222")
        self.artwork_label.pack(pady=12)

        # Right: Controls + Lists
        right_frame = ttk.Frame(main_pane, padding=12)
        main_pane.add(right_frame, weight=3)

        # Search
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(search_frame, text="Search Archive.org:").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=45)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.search_entry.bind("<Return>", lambda e: self.search_albums())

        ttk.Button(search_frame, text="Search", command=self.search_albums, width=10).pack(side="left")

        # Albums
        ttk.Label(right_frame, text="Albums (Archive.org):").pack(anchor="w", pady=(12, 4))
        self.album_listbox = tk.Listbox(right_frame, height=8, font=("Segoe UI", 10), selectmode=tk.SINGLE)
        self.album_listbox.pack(fill="both", expand=False, pady=(0, 6))

        ttk.Button(right_frame, text="Add Album to Playlist", command=self.add_selected_album_to_playlist).pack(pady=(0, 8))

        # Playlist (hybrid tracks)
        playlist_frame = ttk.Frame(right_frame)
        playlist_frame.pack(fill="both", expand=True)

        ttk.Label(playlist_frame, text="Hybrid Playlist:").pack(anchor="w", pady=(0, 4))
        self.playlist_listbox = tk.Listbox(playlist_frame, height=14, font=("Segoe UI", 10), selectmode=tk.SINGLE)
        self.playlist_listbox.pack(fill="both", expand=True, pady=(0, 8))
        self.playlist_listbox.bind("<Double-Button-1>", lambda e: self.play_selected_track())

        # Local + Playlist management buttons
        local_frame = ttk.Frame(right_frame)
        local_frame.pack(fill="x", pady=4)
        ttk.Button(local_frame, text="Add Local Files", command=self.add_local_files, width=15).pack(side="left", padx=6)
        ttk.Button(local_frame, text="Save Playlist (XSPF)", command=self.save_playlist_xspf, width=18).pack(side="left", padx=6)
        ttk.Button(local_frame, text="Load Playlist (XSPF)", command=self.load_playlist_xspf, width=18).pack(side="left", padx=6)
        ttk.Button(local_frame, text="Clear Playlist", command=self.clear_playlist, width=15).pack(side="left", padx=6)

        # Playback controls
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill="x", pady=6)

        self.play_btn = ttk.Button(control_frame, text="Play", command=self.play_selected_track, width=10)
        self.play_btn.pack(side="left", padx=6)

        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_playback, width=10)
        self.stop_btn.pack(side="left", padx=6)

        self.next_btn = ttk.Button(control_frame, text="Next", command=self.play_next, width=10)
        self.next_btn.pack(side="left", padx=6)

        # Credits button
        ttk.Button(control_frame, text="Credits", command=self.show_credits, width=10).pack(side="left", padx=6)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_label.pack(fill="x", side="bottom", ipady=6)

    def show_credits(self):
        credits_text = (
            "Hybrid Music Player\n\n"
            "Created by: SoumyaR (@soucpl)\n"
            "Version: 1.0\n\n"
            "Powered by:\n"
            "• Internet Archive (archive.org) API\n"
            "• Tkinter (GUI)\n"
            "• Pygame (audio playback)\n"
            "• Pillow (image handling)\n"
            "• ElementTree (XSPF XML)\n\n"
            "Thanks to:\n"
            "• The Internet Archive community\n"
            "• Free & open-source software contributors\n\n"
            "Licensed under MIT (feel free to modify & share)"
        )
        messagebox.showinfo("Credits & About", credits_text)

    def set_status(self, msg, error=False):
        prefix = "ERROR: " if error else ""
        self.status_var.set(f"{prefix}{msg}")
        self.root.update_idletasks()

    def search_albums(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Input required", "Please enter a search term")
            return

        self.set_status("Searching…")

        self.album_listbox.delete(0, tk.END)

        try:
            albums = self._search_albums_api(query)
            if not albums:
                self.set_status("No albums found", error=True)
                messagebox.showinfo("Results", "No matching albums found.\nTry a different search term.")
                return

            self.albums_data = albums

            for album in albums:
                title = album.get("title", "Unknown Title")
                creator = album.get("creator", "Unknown")
                year = album.get("date", "—")[:4] if album.get("date") else "—"
                line = f"{title}  —  {creator}  ({year})"
                self.album_listbox.insert(tk.END, line)

            self.set_status(f"Found {len(albums)} albums")
        except Exception as e:
            print(f"Search failed: {e}")
            self.set_status(f"Search failed: {str(e)}", error=True)
            messagebox.showerror("Search Error", f"Could not connect to Archive.org.\n{str(e)}")

    def _search_albums_api(self, query, max_total=300, results_per_page=100):
        base_url = "https://archive.org/advancedsearch.php"
        search_q = (
            'mediatype:audio AND '
            '(collection:album_recordings OR collection:netlabels OR collection:community_audio OR collection:opensource_audio) '
            'AND NOT access-restricted-item:true '
            'AND (title:"{q}" OR creator:"{q}" OR subject:"{q}")'
        ).format(q=query.replace('"', '\\"'))

        all_docs = []
        page = 1

        while len(all_docs) < max_total:
            params = {
                "q": search_q,
                "fl[]": ["identifier", "title", "creator", "date"],
                "sort[]": "-downloads",
                "rows": results_per_page,
                "output": "json",
                "page": page
            }
            try:
                r = requests.get(base_url, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                docs = data.get("response", {}).get("docs", [])

                if not docs:
                    break

                all_docs.extend(docs)

                if len(docs) < results_per_page:
                    break

                page += 1
                if page > 20:
                    break

            except requests.exceptions.RequestException as e:
                print(f"Network error on page {page}: {e}")
                self.set_status(f"Network issue (page {page})", error=True)
                break
            except ValueError as e:
                print(f"JSON decode error on page {page}: {e}")
                break
            except Exception as e:
                print(f"Unexpected error on page {page}: {e}")
                break

        return all_docs[:max_total]

    def add_selected_album_to_playlist(self):
        selection = self.album_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection required", "Please select an album first")
            return

        idx = selection[0]
        try:
            album = self.albums_data[idx]
        except IndexError:
            self.set_status("Invalid album selection", error=True)
            return

        identifier = album.get("identifier")
        if not identifier:
            self.set_status("Album missing identifier", error=True)
            return

        self.set_status(f"Loading {album.get('title', identifier)} …")

        try:
            tracks, cover_url = self._get_tracks_and_cover(identifier)

            if not tracks:
                self.set_status("No playable audio files found", error=True)
                return

            # Add to hybrid playlist as remote
            for track in tracks:
                self.current_playlist.append({
                    'name': os.path.basename(track['name']),
                    'type': 'remote',
                    'url': track['url']
                })

            self._update_playlist_display()
            self._display_cover_art(cover_url)
            self.set_status(f"Added {len(tracks)} remote tracks to playlist")
        except Exception as e:
            print(f"Album load failed: {e}")
            self.set_status(f"Failed to load album: {str(e)}", error=True)

    def _get_tracks_and_cover(self, identifier):
        url = f"https://archive.org/metadata/{identifier}"
        try:
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            meta = r.json()
            files = meta.get("files", []) or []

            tracks = []
            cover_candidates = []

            for f in files:
                name = f.get("name", "")
                if not name:
                    continue
                fmt = f.get("format", "").upper()
                name_lower = name.lower()

                if any(x in fmt for x in ["MP3", "VORBIS", "OGG", "FLAC"]):
                    tracks.append({
                        'name': name,
                        'url': f"https://archive.org/download/{identifier}/{name}"
                    })

                if any(ext in name_lower for ext in [".jpg", ".jpeg", ".png"]):
                    score = 0
                    if any(kw in name_lower for kw in ["cover", "front"]): score += 3
                    elif any(kw in name_lower for kw in ["folder", "albumart"]): score += 2
                    elif "art" in name_lower: score += 1
                    cover_candidates.append((score, name))

            tracks.sort(key=lambda x: x["name"])

            cover_url = None
            if cover_candidates:
                best = max(cover_candidates, key=lambda x: x[0])
                cover_url = f"https://archive.org/download/{identifier}/{best[1]}"

            return tracks, cover_url

        except requests.exceptions.RequestException as e:
            print(f"Metadata network error: {e}")
            self.set_status("Cannot reach metadata", error=True)
            return [], None
        except ValueError as e:
            print(f"Metadata JSON error: {e}")
            return [], None
        except Exception as e:
            print(f"Metadata processing error: {e}")
            return [], None

    def add_local_files(self):
        filetypes = [("Audio files", "*.mp3 *.ogg *.wav *.flac")]
        paths = filedialog.askopenfilenames(title="Select Local Audio Files", filetypes=filetypes)
        if not paths:
            return

        added = 0
        for path in paths:
            if os.path.exists(path) and os.path.isfile(path):
                self.current_playlist.append({
                    'name': os.path.basename(path),
                    'type': 'local',
                    'path': path
                })
                added += 1
            else:
                print(f"Invalid local file: {path}")

        self._update_playlist_display()
        self.set_status(f"Added {added} local files to playlist")

    def save_playlist_xspf(self):
        if not self.current_playlist:
            messagebox.showwarning("Empty Playlist", "Nothing to save")
            return

        filepath = filedialog.asksaveasfilename(title="Save Playlist (XSPF)", defaultextension=".xspf", filetypes=[("XSPF files", "*.xspf")])
        if not filepath:
            return

        try:
            playlist = ET.Element("playlist", version="1", xmlns="http://xspf.org/ns/0/")
            tracklist = ET.SubElement(playlist, "trackList")

            for track in self.current_playlist:
                track_elem = ET.SubElement(tracklist, "track")
                title = ET.SubElement(track_elem, "title")
                title.text = track['name']
                location = ET.SubElement(track_elem, "location")
                if track['type'] == 'local':
                    location.text = f"file://{quote(track['path'], safe='/:')}"
                else:
                    location.text = track['url']

            tree = ET.ElementTree(playlist)
            tree.write(filepath, encoding="utf-8", xml_declaration=True)
            self.set_status(f"Playlist saved to {os.path.basename(filepath)} (XSPF)")
        except Exception as e:
            print(f"XSPF save failed: {e}")
            self.set_status(f"Save failed: {str(e)}", error=True)

    def load_playlist_xspf(self):
        filepath = filedialog.askopenfilename(title="Load Playlist (XSPF)", filetypes=[("XSPF files", "*.xspf")])
        if not filepath:
            return

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            if root.tag != "playlist":
                raise ValueError("Invalid XSPF format")

            loaded_tracks = []
            for track_elem in root.findall(".//track"):
                name = track_elem.findtext("title") or "Unknown"
                loc = track_elem.findtext("location")
                if not loc:
                    continue

                if loc.startswith("file://"):
                    path = loc[7:].replace("%20", " ")
                    if os.path.exists(path):
                        loaded_tracks.append({
                            'name': name,
                            'type': 'local',
                            'path': path
                        })
                elif loc.startswith("http"):
                    loaded_tracks.append({
                        'name': name,
                        'type': 'remote',
                        'url': loc
                    })

            if loaded_tracks:
                self.current_playlist.extend(loaded_tracks)
                self._update_playlist_display()
                self.set_status(f"Loaded {len(loaded_tracks)} tracks from {os.path.basename(filepath)} (XSPF)")
            else:
                self.set_status("No valid tracks found in XSPF", error=True)
        except Exception as e:
            print(f"XSPF load failed: {e}")
            self.set_status(f"Load failed: {str(e)}", error=True)

    def clear_playlist(self):
        self.current_playlist = []
        self._update_playlist_display()
        self.current_track_index = -1
        self.stop_playback()
        self._display_cover_art(None)
        self.set_status("Playlist cleared")

    def _update_playlist_display(self):
        self.playlist_listbox.delete(0, tk.END)
        for track in self.current_playlist:
            source = "[Local]" if track['type'] == 'local' else "[Remote]"
            self.playlist_listbox.insert(tk.END, f"{source} {track['name']}")

    def _display_cover_art(self, url):
        self.artwork_label.config(image="", text="[No artwork]")
        self.photo_image = None

        if self.temp_image_file and os.path.exists(self.temp_image_file):
            try:
                os.remove(self.temp_image_file)
            except:
                pass
            self.temp_image_file = None

        if not url:
            return

        try:
            r = requests.get(url, stream=True, timeout=10)
            r.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                for chunk in r.iter_content(16384):
                    if chunk:
                        tmp.write(chunk)
                self.temp_image_file = tmp.name

            img = Image.open(self.temp_image_file)
            img = img.resize((220, 220), Image.Resampling.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(img)
            self.artwork_label.config(image=self.photo_image, text="")
        except Exception as e:
            print(f"Artwork download/display failed: {e}")
            self.artwork_label.config(text="[Artwork failed]")

    def play_selected_track(self):
        sel = self.playlist_listbox.curselection()
        if not sel:
            if not self.current_playlist:
                messagebox.showwarning("No tracks", "Playlist is empty")
                return
            idx = 0
        else:
            idx = sel[0]

        if idx < 0 or idx >= len(self.current_playlist):
            self.set_status("Invalid track index", error=True)
            return

        self.current_track_index = idx
        self._play_track_at_index(idx)

    def _play_track_at_index(self, idx):
        track = self.current_playlist[idx]
        display_name = track['name']
        self.set_status(f"Preparing: {display_name}")

        self.stop_playback(cleanup_only=True)

        def load_and_play():
            try:
                if track['type'] == 'local':
                    audio_path = track['path']
                    if not os.path.exists(audio_path):
                        raise FileNotFoundError(f"Local file missing: {audio_path}")
                    self.temp_audio_file = None  # No temp for local
                else:  # remote
                    r = requests.get(track['url'], stream=True, timeout=20)
                    r.raise_for_status()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(display_name)[1] or ".mp3") as tmp:
                        for chunk in r.iter_content(chunk_size=32768):
                            if chunk:
                                tmp.write(chunk)
                        audio_path = tmp.name
                    self.temp_audio_file = audio_path

                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                self.is_playing = True
                self.set_status(f"Playing: {display_name}")
                self.root.after(700, self._check_playback_status)

            except FileNotFoundError as e:
                self.set_status(f"File not found: {str(e)}", error=True)
            except requests.exceptions.RequestException as e:
                self.set_status(f"Download failed: {str(e)}", error=True)
            except pygame.error as e:
                self.set_status(f"Playback init failed: {str(e)}", error=True)
            except Exception as e:
                self.set_status(f"Playback error: {str(e)}", error=True)
            finally:
                self.is_playing = False if not pygame.mixer.music.get_busy() else True

        threading.Thread(target=load_and_play, daemon=True).start()

    def _check_playback_status(self):
        if not self.is_playing:
            return

        try:
            if not pygame.mixer.music.get_busy():
                self.is_playing = False
                # Auto-download if remote and played completely
                if self.current_track_index >= 0:
                    track = self.current_playlist[self.current_track_index]
                    if track['type'] == 'remote' and self.temp_audio_file:
                        self._auto_download_track(track, self.temp_audio_file)
                self.stop_playback(cleanup_only=True)
                self.play_next()
            else:
                self.root.after(1000, self._check_playback_status)
        except Exception as e:
            print(f"Playback status check error: {e}")
            self.is_playing = False

    def _auto_download_track(self, track, temp_path):
        def download():
            try:
                local_path = os.path.join(self.download_dir, track['name'])
                os.replace(temp_path, local_path)  # Move temp to permanent
                self.temp_audio_file = None  # Clear temp since moved

                # Update playlist to local
                track['type'] = 'local'
                track['path'] = local_path
                del track['url']
                self._update_playlist_display()

                self.set_status(f"Downloaded: {track['name']} to {self.download_dir}")
            except Exception as e:
                print(f"Auto-download failed: {e}")
                self.set_status(f"Auto-download failed: {str(e)}", error=True)

        threading.Thread(target=download, daemon=True).start()

    def play_next(self):
        if self.current_track_index < len(self.current_playlist) - 1:
            self.current_track_index += 1
            self.playlist_listbox.selection_clear(0, tk.END)
            self.playlist_listbox.selection_set(self.current_track_index)
            self.playlist_listbox.see(self.current_track_index)
            self._play_track_at_index(self.current_track_index)
        else:
            self.set_status("End of playlist reached")

    def stop_playback(self, cleanup_only=False):
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
        except:
            pass

        if self.temp_audio_file and os.path.exists(self.temp_audio_file):
            try:
                os.remove(self.temp_audio_file)
            except:
                pass
            self.temp_audio_file = None

        self.is_playing = False

        if not cleanup_only:
            self.set_status("Stopped")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArchiveMusicPlayer(root)
    root.mainloop()
