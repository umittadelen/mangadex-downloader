import requests
import re
import os
import time
import threading
from PIL import Image, UnidentifiedImageError
from concurrent.futures import ThreadPoolExecutor

def get_chapter_id(url: str) -> str | None:
    match = re.match(r'https:\/\/mangadex\.org\/chapter\/([0-9a-fA-F-]{36})', url)
    return match.group(1) if match else None

def fetch_chapter_data(chapter_id: str) -> dict | None:
    api_url = f'https://api.mangadex.org/at-home/server/{chapter_id}'
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Failed to fetch chapter data: {e}")
        return None

def download_image(idx: int, filename: str, base_url: str, hash_: str, retries=4) -> str | None:
    url = f"{base_url}/{hash_}/{filename}"
    local = f"page_{idx}.jpg"
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(local, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
            if os.path.getsize(local) < 10 * 1024:
                raise Exception("File too small")
            return local
        except Exception as e:
            if os.path.exists(local):
                os.remove(local)
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"\nFailed to download {url}: {e}")
    return None

def print_progress(done, total, bar_len=40):
    percent = done / total
    filled = int(bar_len * percent)
    bar = '█' * filled + '-' * (bar_len - filled)
    print(f"\rDownloading: |{bar}| {done}/{total} pages", end='', flush=True)

def collect_valid_images(image_files: list[str]) -> list[Image.Image]:
    valid = []
    for f in image_files:
        try:
            img = Image.open(f)
            img.verify()
            img = Image.open(f).convert("RGB")
            valid.append(img)
        except (UnidentifiedImageError, OSError):
            print(f"Skipping corrupted image: {f}")
            os.remove(f)
    return valid

def main():
    url = input("Enter MangaDex chapter URL: ").strip()
    chapter_id = get_chapter_id(url)
    if not chapter_id:
        print("Invalid URL~! 💔 Make sure it's a valid MangaDex chapter URL.")
        return

    print("Nyaa~ Fetching chapter data... 🐾")
    data = fetch_chapter_data(chapter_id)
    if not data:
        print("Error fetching chapter data! 😿")
        return

    hash_ = data["chapter"]["hash"]
    pages = data["chapter"]["data"]
    base_url = "https://uploads.mangadex.org/data"
    total = len(pages)
    max_workers = min(12, total)  # 8-12 is usually optimal

    image_files = [None] * total
    completed = 0
    completed_lock = threading.Lock()

    def task(idx, filename):
        nonlocal completed
        result = download_image(idx + 1, filename, base_url, hash_)
        with completed_lock:
            completed += 1
            print_progress(completed, total)
        return idx, result

    print_progress(0, total)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task, idx, fname) for idx, fname in enumerate(pages)]
        for future in futures:
            idx, result = future.result()
            if result:
                image_files[idx] = result
    print()  # Newline after progress bar

    # Remove None entries and corrupted images
    image_files = [f for f in image_files if f]
    valid_images = collect_valid_images(image_files)

    if valid_images:
        pdf_filename = f"{chapter_id}.pdf"
        valid_images[0].save(pdf_filename, save_all=True, append_images=valid_images[1:])
        print(f"PDF saved as '{pdf_filename}'! 🎉📘")
        for f in image_files:
            if os.path.exists(f):
                os.remove(f)
    else:
        print("No valid images found~! Something went wrong... 😔")

if __name__ == "__main__":
    main()