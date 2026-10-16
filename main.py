import os
import time
import requests
import random
import urllib.parse
from moviepy.editor import *
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from gtts import gTTS

def get_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
    )
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def get_trending_data(youtube):
    print("Fetching trending videos in India...")
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="IN", 
            maxResults=5
        )
        response = request.execute()
        
        selected_item = random.choice(response['items'])
        top_video = selected_item['snippet']
        title = top_video['title']
        
        tags = top_video.get('tags', [])
        hashtags = [f"#{tag.replace(' ', '')}" for tag in tags[:3]]
        if len(hashtags) < 3:
            hashtags.extend(["#trending", "#viral", "#shorts"][:3 - len(hashtags)])
            
        category_id = top_video.get('categoryId', '24')
        return title, hashtags, category_id
    except HttpError as e:
        print(f"YouTube API Error: {e}")
        return "Top Trending Topic In India", ["#trending", "#viral", "#shorts"], "24"

def generate_ai_visual(topic):
    print(f"Generating free AI visual for: {topic}...")
    prompt = f"Cinematic vertical 9:16 background, dramatic lighting, 8k wallpaper representing: {topic}"
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    img_filename = "ai_frame.jpg"
    
    for attempt in range(3):
        try:
            print(f"Image generation attempt {attempt + 1}/3...")
            # Increased timeout to 120 seconds to prevent Read timed out errors
            response = requests.get(image_url, headers=headers, timeout=120)
            response.raise_for_status()
            
            with open(img_filename, "wb") as f:
                f.write(response.content)
                
            print("AI Visual generated successfully!")
            return img_filename
            
        except requests.exceptions.RequestException as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            if attempt < 2:
                print("Retrying in 10 seconds...")
                time.sleep(10)
            else:
                raise Exception("Failed to generate AI visual after 3 attempts.")

def generate_voice(text, filename="voice.mp3"):
    print("Generating voiceover...")
    tts = gTTS(text=text, lang='en', tld='co.in')
    tts.save(filename)
    return filename

def generate_short(trending_title):
    print("Generating Short...")
    
    script = f"Trending now in India! Everyone is watching: {trending_title}. Don't miss out on today's most popular video!"
    
    generate_voice(script)
    img_path = generate_ai_visual(trending_title)
    
    audio = AudioFileClip("voice.mp3")
    duration = audio.duration + 1
    
    raw_clip = ImageClip(img_path).set_duration(duration)
    animated_bg = raw_clip.resize(lambda t: 1 + 0.03 * t).set_position(('center', 'center'))
    background = CompositeVideoClip([animated_bg], size=(1080, 1920)).set_duration(duration)
    
    text_clip = TextClip(
        trending_title,
        fontsize=60,
        color='white',
        font='Liberation-Sans-Bold', 
        method='caption',
        size=(900, None),
        align='center'
    ).set_position('center').set_duration(duration)
    
    final = CompositeVideoClip([background, text_clip]).set_audio(audio)
    
    output = "short.mp4"
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")
    
    background.close()
    audio.close()
    return output

def upload_video(youtube, video_file, title, hashtags, category_id):
    print("Uploading to YouTube...")
    
    hashtag_str = " ".join(hashtags)
    max_title_len = 95 - len(hashtag_str)
    short_title = (title[:max_title_len] + "...") if len(title) > max_title_len else title
    full_title = f"{short_title} {hashtag_str}"
    
    body = {
        "snippet": {
            "title": full_title,
            "description": f"Trending topic overview: {title}\n\n{hashtag_str}",
            "tags": [h.strip('#') for h in hashtags],
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_file, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    max_retries = 5

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except (HttpError, Exception) as e:
            if retries >= max_retries:
                raise Exception(f"Upload failed after {max_retries} retries: {e}")
            retries += 1
            sleep_time = 2 ** retries
            print(f"Retrying upload in {sleep_time}s...")
            time.sleep(sleep_time)

    print(f"Upload complete! Video ID: {response['id']}")
    return response['id']

if __name__ == "__main__":
    try:
        youtube = get_youtube_service()
        title, hashtags, category_id = get_trending_data(youtube)
        video_path = generate_short(title)
        upload_video(youtube, video_path, title, hashtags, category_id)
        print("Success!")
    except Exception as e:
        print(f"Critical Error: {e}")
        exit(1)
