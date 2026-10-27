import os
import re
import urllib.request
from datetime import datetime
import feedparser
from duckduckgo_search import DDGS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips
import googleapiclient.discovery
import googleapiclient.http
from google.oauth2.credentials import Credentials

def get_trends():
    url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
    feed = feedparser.parse(url)
    titles = [entry.title for entry in feed.entries]
    return titles

def clean_tag(text):
    clean = re.sub(r'[^a-zA-Z0-9]', '', text)
    return "#" + clean.lower()

def prepare_image(img_path):
    img = Image.open(img_path).convert("RGB")
    target_ratio = 1080 / 1920
    w, h = img.size
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) / 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) / 2
        img = img.crop((0, top, w, top + new_h))
    
    img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
    img.save(img_path)

def add_text_overlay(img_path, text):
    img = Image.open(img_path)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except IOError:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (1080 - text_w) / 2
    y = 1920 - 300
    
    draw.rectangle([x - 20, y - 20, x + text_w + 20, y + text_h + 20], fill="black")
    draw.text((x, y), text, font=font, fill="white")
    img.save(img_path)

def upload_video(file_path, title):
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")
    
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    
    body = {
        "snippet": {
            "title": title,
            "description": "Trending now. " + title,
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print("Uploaded video ID:", response.get("id"))

def main():
    trends = get_trends()
    if not trends:
        print("No trends found.")
        return
        
    topic = trends[0]
    tag_trends = trends[1:4]
    
    hashtags = clean_tag(tag_trends[0]) + " " + clean_tag(tag_trends[1]) + " " + clean_tag(tag_trends[2])
    base_title = f"Nobody is talking about {topic} "
    
    if len(base_title) + len(hashtags) > 100:
        allowed = 100 - len(hashtags) - 1
        base_title = base_title[:allowed]
        
    final_title = base_title + " " + hashtags
    print("Final Title:", final_title)
    
    results = DDGS().images(topic, max_results=5)
    image_files = []
    
    for i, res in enumerate(results):
        try:
            url = res["image"]
            filename = f"image_{i}.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response, open(filename, "wb") as out_file:
                out_file.write(response.read())
            prepare_image(filename)
            image_files.append(filename)
        except Exception as e:
            print("Failed to get image:", e)
            
    if len(image_files) < 2:
        print("Not enough images saved.")
        return
        
    add_text_overlay(image_files[-1], "And that is exactly why...")
    add_text_overlay(image_files[0], "...this trend is taking over!")
    
    clips = []
    for img in image_files:
        clip = ImageClip(img).set_duration(3)
        clips.append(clip)
        
    clips.append(ImageClip(image_files[0]).set_duration(3))
    
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile("final.mp4", fps=24, codec="libx264")
    
    upload_video("final.mp4", final_title)

if __name__ == "__main__":
    main()
    
