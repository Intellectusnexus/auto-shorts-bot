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
    try:
        request = youtube.videos().list(part="snippet", chart="mostPopular", regionCode="IN", maxResults=10)
        response = request.execute()
        
        selected = random.choice(response["items"][:5])
        original_title = selected["snippet"]["title"].replace("'", "")
        
        strong_title = original_title[:70] + ("..." if len(original_title) > 70 else "")
        return strong_title, original_title, ["#trending", "#viral", "#shorts"], "24"
    except Exception as e:
        print(f"Failed to fetch trend: {e}")
        fallback = "The craziest viral moment of the week"
        return fallback, fallback, ["#trending", "#viral", "#shorts"], "24"

def get_explainer_script(strong_title, original_topic):
    return [
        {"text": f"Everyone is talking about {strong_title}.", "visual_prompt": f"Cinematic wide shot, epic atmosphere, representing {original_topic}"},
        {"text": "But most people completely missed the craziest detail hidden in plain sight.", "visual_prompt": "Camera zooming in fast, glowing elements, revealing a secret detail"},
        {"text": "When you look closely, it completely changes how you see the whole thing.", "visual_prompt": "Dramatic lighting shift, mind-blowing revelation, dynamic angles, highly detailed"},
        {"text": "What do you actually think about this? Drop a comment and subscribe for more.", "visual_prompt": "High energy cinematic outro, neon lights, glitch transitions"}
    ]

async def generate_voice(text, filename):
    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaNeural", rate="+15%")
    await communicate.save(filename)

def extract_last_frame(video_file, output_image):
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.5", "-i", video_file, "-update", "1", "-q:v", "2", output_image], check=True)

async def generate_short(strong_title, original_topic):
    script_parts = get_explainer_script(strong_title, original_topic)
    clips = []
    
    print("Generating base establishing scene...")
    safe_topic = urllib.parse.quote(original_topic[:50])
    encoded_prompt = f"Cinematic vertical 9:16 portrait, viral trending moment, {safe_topic}, epic atmosphere, highly detailed, 8k"
    base_img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(encoded_prompt)}?width=1080&height=1920&nologo=true&model=flux"
    current_frame = "current_frame.jpg"
    
    with open(current_frame, "wb") as f:
        f.write(requests.get(base_img_url).content)

    for i, part in enumerate(script_parts):
        print(f"Generating Scene {i+1}/4 (Chaining from previous frame)...")
        audio_file = f"voice_{i}.mp3"
        raw_video = f"raw_video_{i}.mp4"
        clip_file = f"clip_{i}.mp4"
        
        await generate_voice(part["text"], audio_file)
        
        uploaded_image_url = fal_client.upload_file(current_frame)
        
        try:
            result = fal_client.subscribe(
                "fal-ai/kling-video/v1/standard/image-to-video",
                arguments={
                    "image_url": uploaded_image_url,
                    "prompt": f"Cinematic vertical 9:16, {part['visual_prompt']}, highly detailed, 8k",
                    "aspect_ratio": "9:16"
                }
            )
            vid_data = requests.get(result['video']['url'], timeout=60).content
            with open(raw_video, "wb") as f:
                f.write(vid_data)
        except Exception as e:
            print(f"Kling API failed for scene {i}: {e}")
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", current_frame, "-t", "5", "-c:v", "libx264", "-pix_fmt", "yuv420p", raw_video], check=True)

        extract_last_frame(raw_video, current_frame)
        
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", raw_video, "-i", audio_file,
            "-filter_complex", 
            f"[0:v]tpad=stop_mode=clone:stop_duration=3,scale=1080:1920,drawtext=text='{strong_title}':fontcolor=white:fontsize=52:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.35[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", clip_file
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        clips.append(clip_file)

    print("Stitching scenes...")
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
    video_path = asyncio.run(generate_short(strong_title, original_topic))
    upload_video(youtube, video_path, strong_title, hashtags, category_id)
    
