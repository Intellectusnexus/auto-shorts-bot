import os
import time
import requests
import random
import urllib.parse
import edge_tts
import asyncio
import subprocess
import fal_client
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
    
    strong_title = f"The Dark Truth About {original_title.strip()}".replace("'", "") 
    return strong_title, original_title, ["#facts", "#psychology", "#space", "#shorts"], "27"

def get_explainer_script(strong_title, original_topic):
    return [
        {"text": f"{strong_title}. Most people have absolutely no idea about the hidden truth behind this.", "visual_prompt": f"wide shot, mysterious atmosphere, discovering {original_topic}"},
        {"text": "For years, the mainstream narrative has kept the real facts completely hidden from the public eye.", "visual_prompt": "dark shadowy figures, classified documents, secret archive, moody lighting"},
        {"text": f"But recent leaks reveal that {original_topic} is actually far more terrifying than anyone ever imagined.", "visual_prompt": f"dramatic close up, shocking revelation, cinematic lighting, {original_topic}"},
        {"text": "The rabbit hole goes even deeper. Subscribe right now if you want to uncover the full story.", "visual_prompt": "glitch effect, dark hacker room, glowing screens, mysterious"}
    ]

async def generate_voice(text, filename):
    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaNeural")
    await communicate.save(filename)

def generate_ai_video(prompt, filename):
    try:
        result = fal_client.subscribe(
            "fal-ai/kling-video/v1/standard/text-to-video",
            arguments={"prompt": f"Cinematic vertical 9:16, {prompt}, highly detailed, moody", "aspect_ratio": "9:16"}
        )
        response = requests.get(result['video']['url'], timeout=60)
        with open(filename, "wb") as f:
            f.write(response.content)
    except Exception:
        # Fallback to 5 seconds of dark background if API fails
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x080814:s=1080x1920:d=5", filename], check=True)

def generate_short(strong_title, original_topic):
    script_parts = get_explainer_script(strong_title, original_topic)
    clips = []
    
    for i, part in enumerate(script_parts):
        audio_file = f"voice_{i}.mp3"
        video_file = f"video_{i}.mp4"
        clip_file = f"clip_{i}.mp4"
        
        asyncio.run(generate_voice(part["text"], audio_file))
        generate_ai_video(part["visual_prompt"], video_file)
        
        # -stream_loop -1 loops the 5s AI video until the audio finishes
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", video_file, "-i", audio_file,
            "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=text='{strong_title}':fontcolor=white:fontsize=52:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.35",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", clip_file
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        clips.append(clip_file)

    with open("concat.txt", "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
            
    final_output = "explainer_short.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", final_output], check=True)
    
    return final_output

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
    
