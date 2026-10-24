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
    try:
        request = youtube.videos().list(part="snippet", chart="mostPopular", regionCode="IN", maxResults=10)
        response = request.execute()
        selected = random.choice(response["items"][:5])
        original_title = selected["snippet"]["title"].replace("'", "")
        strong_title = original_title[:70] + ("..." if len(original_title) > 70 else "")
        return strong_title, original_title, ["#trending", "#viral", "#shorts"], "24"
    except Exception:
        return "The craziest viral moment of the week", "viral trending topic", ["#trending", "#viral"], "24"

def get_explainer_script(strong_title, original_topic):
    return [
        {"text": f"Everyone is talking about {strong_title}.", "prompt": f"Cinematic wide shot, {original_topic}, epic lighting"},
        {"text": "But most people completely missed the craziest detail hidden in plain sight.", "prompt": f"Close up, mysterious hidden detail about {original_topic}, glowing"},
        {"text": "When you look closely, it completely changes how you see the whole thing.", "prompt": f"Mind blowing revelation, {original_topic}, dramatic shadows"},
        {"text": "What do you actually think about this? Drop a comment and subscribe for more.", "prompt": f"Cyberpunk glitch, hacker matrix, neon lights"}
    ]

async def generate_voice(text, filename):
    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaNeural", rate="+15%")
    await communicate.save(filename)

def get_ai_image(prompt, filename):
    seed = random.randint(1, 999999)
    # Slicing the prompt ensures the URL does not become too long and cause a server rejection
    safe_prompt = urllib.parse.quote(f"Vertical 9:16, {prompt[:150]}, highly detailed, 8k")
    image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1920&nologo=true&model=flux&seed={seed}"
    
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status() # Force exception on 404/500 errors
        
        # Verify the returned content is actually an image before writing it
        if 'image' not in response.headers.get('Content-Type', ''):
            raise ValueError("API returned non-image data")
            
        with open(filename, "wb") as f:
            f.write(response.content)
            
    except Exception as e:
        print(f"Image fetch failed ({e}). Using synthetic fallback.")
        # Generates a valid deep blue solid color JPEG so FFmpeg doesn't crash
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x080814:s=1080x1920", "-vframes", "1", filename], check=True)

async def generate_short(strong_title, original_topic):
    script_parts = get_explainer_script(strong_title, original_topic)
    clips = []
    
    for i, part in enumerate(script_parts):
        print(f"Generating Optimized Infographic Scene {i+1}/4...")
        audio_file = f"voice_{i}.mp3"
        img_file = f"image_{i}.jpg"
        clip_file = f"clip_{i}.mp4"
        
        await generate_voice(part["text"], audio_file)
        await asyncio.to_thread(get_ai_image, part["prompt"], img_file)
        
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_file, "-i", audio_file,
            "-filter_complex", 
            f"[0:v]scale=1080:1920,zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=24,colorlevels=romax=0.5:gomax=0.5:bomax=0.5[bg];"
            f"[1:a]showwaves=s=1080x250:mode=cline:colors=0x00FF99[wave];"
            f"[bg][wave]overlay=0:H-350[v1];"
            f"[v1]drawtext=text='{strong_title}':fontcolor=white:fontsize=52:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.2[outv]",
            "-map", "[outv]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
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
    
