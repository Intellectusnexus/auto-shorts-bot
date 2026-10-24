import os
import time
import requests
import random
import urllib.parse
import edge_tts
import asyncio
import subprocess
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
    )
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def get_trending_data(youtube):
    allowed_keywords = ["psychology", "manipulation", "narcissist", "toxic", "mind", "behavior", "space", "history", "money", "brain"]
    fallback_topics = ["What really happens if you fall into a black hole", "The hidden reason rich people think differently"]
    try:
        request = youtube.videos().list(part="snippet", chart="mostPopular", regionCode="IN", maxResults=30)
        response = request.execute()
        good_videos = [item for item in response["items"] if any(k in item["snippet"]["title"].lower() for k in allowed_keywords)]
        original_title = random.choice(good_videos)["snippet"]["title"] if good_videos else random.choice(fallback_topics)
    except Exception:
        original_title = random.choice(fallback_topics)
    
    strong_title = f"The Dark Truth About {original_title.strip()}".replace("'", "") # Stripping quotes for FFmpeg compatibility
    return strong_title, original_title, ["#facts", "#psychology", "#space", "#shorts"], "27"

async def generate_voice(text, filename="voice.mp3"):
    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaNeural")
    await communicate.save(filename)
    return filename

def generate_ai_visual(topic):
    encoded_prompt = urllib.parse.quote(f"Cinematic vertical 9:16, dark atmosphere, highly detailed, moody, {topic}, no text")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&model=flux"
    try:
        response = requests.get(image_url, timeout=30)
        with open("ai_frame.jpg", "wb") as f:
            f.write(response.content)
        return "ai_frame.jpg"
    except Exception:
        # Fallback to a solid dark blue image if generation fails
        subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=0x080814:s=1080x1920", "-vframes", "1", "ai_frame.jpg"], check=True)
        return "ai_frame.jpg"

def generate_short(strong_title, original_topic):
    script = f"{strong_title}. Most people have no idea this is true. Stay till the end."
    asyncio.run(generate_voice(script))
    img_path = generate_ai_visual(strong_title)
    output = "short.mp4"
    
    # FFmpeg command replaces MoviePy completely. Renders instantly.
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loop", "1", "-framerate", "24", "-i", img_path, "-i", "voice.mp3",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=text='{strong_title}':fontcolor=white:fontsize=52:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.35",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", output
    ]
    
    subprocess.run(ffmpeg_cmd, check=True)
    return output

def upload_video(youtube, video_file, title, hashtags, category_id):
    full_title = (f"{title} {' '.join(hashtags)}")[:97] + "..."
    body = {
        "snippet": {"title": full_title, "description": f"{title}\n\n{' '.join(hashtags)}", "tags": [h.strip("#") for h in hashtags], "categoryId": category_id},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_file, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
    return response["id"]

if __name__ == "__main__":
    youtube = get_youtube_service()
    strong_title, original_topic, hashtags, category_id = get_trending_data(youtube)
    video_path = generate_short(strong_title, original_topic)
    upload_video(youtube, video_path, strong_title, hashtags, category_id)
    
