import os
import time
import requests
import random
import urllib.parse
import edge_tts
import asyncio
from moviepy.editor import *
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ====================== YOUTUBE AUTH ======================
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


# ====================== TRENDING + NICHE FILTER ======================
def get_trending_data(youtube):
    print("Fetching trending videos and filtering for high-quality niches...")

    allowed_keywords = [
        "psychology", "manipulation", "narcissist", "toxic", "mind", "behavior",
        "black hole", "universe", "space", "cosmos", "galaxy", "nasa", "astronomy",
        "history", "ancient", "mystery", "secret", "forgotten", "dark history",
        "money", "rich", "poor", "wealth", "millionaire", "finance",
        "brain", "sleep", "human body", "health"
    ]

    fallback_topics = [
        "What really happens if you fall into a black hole",
        "The dark psychology behind why people stay in toxic relationships",
        "Why most people stay poor without realizing it",
        "The scariest fact about the size of the universe",
        "Strange historical events they never taught you in school",
        "What your brain does while you sleep that is terrifying",
        "The hidden reason rich people think differently",
        "A dark truth about human behavior most people ignore"
    ]

    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="IN",
            maxResults=30
        )
        response = request.execute()

        good_videos = []
        for item in response["items"]:
            title_lower = item["snippet"]["title"].lower()
            if any(keyword in title_lower for keyword in allowed_keywords):
                good_videos.append(item)

        if good_videos:
            selected = random.choice(good_videos)
            original_title = selected["snippet"]["title"]
            print(f"Selected niche video: {original_title}")
        else:
            original_title = random.choice(fallback_topics)
            print(f"No good trend found. Using fallback: {original_title}")

        # Create a stronger title
        strong_title = create_strong_title(original_title)

        hashtags = ["#facts", "#psychology", "#space", "#shorts"]
        category_id = "27"  # Education / Science style

        return strong_title, original_title, hashtags, category_id

    except Exception as e:
        print(f"Error fetching trends: {e}")
        original_title = random.choice(fallback_topics)
        strong_title = create_strong_title(original_title)
        return strong_title, original_title, ["#facts", "#shorts"], "27"


def create_strong_title(topic):
    """Turn any topic into a high-curiosity title"""
    topic = topic.strip()

    templates = [
        f"The Dark Truth About {topic}",
        f"What They Never Tell You About {topic}",
        f"Why {topic} Is More Terrifying Than You Think",
        f"The Real Reason Behind {topic}",
        f"Most People Are Wrong About {topic}",
        f"A Disturbing Fact About {topic}"
    ]
    return random.choice(templates)


# ====================== SCRIPT GENERATION ======================
def create_script(strong_title, original_topic):
    """Create a high-retention short script"""
    scripts = [
        f"{strong_title}. Most people have no idea this is true. Stay till the end.",
        f"{strong_title}. This will change how you see everything. Watch carefully.",
        f"Here's something most people get completely wrong about {original_topic}. {strong_title}.",
        f"{strong_title}. Once you know this, you can't unsee it."
    ]
    return random.choice(scripts)


# ====================== FREE HIGH QUALITY VOICE ======================
async def generate_voice(text, filename="voice.mp3"):
    print("Generating high quality free voice...")
    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaNeural")  # Natural Indian English female
    await communicate.save(filename)
    return filename


# ====================== AI IMAGE ======================
def generate_ai_visual(topic):
    print(f"Generating cinematic AI visual for: {topic}")

    prompt = (
        f"Cinematic vertical 9:16, dramatic lighting, dark atmosphere, "
        f"highly detailed, 8k, moody, emotional, professional photography style, "
        f"representing: {topic}, no text, no watermark"
    )
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&model=flux"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    img_filename = "ai_frame.jpg"

    for attempt in range(4):
        try:
            print(f"Image attempt {attempt + 1}/4...")
            response = requests.get(image_url, headers=headers, timeout=90)
            response.raise_for_status()

            with open(img_filename, "wb") as f:
                f.write(response.content)

            print("AI Visual generated successfully!")
            return img_filename

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 3:
                time.sleep(8)
            else:
                print("Failed to generate image. Using dark fallback.")
                return None


# ====================== VIDEO CREATION ======================
def generate_short(strong_title, original_topic):
    print("Generating high quality Short...")

    script = create_script(strong_title, original_topic)
    print(f"Script: {script}")

    # Generate voice
    asyncio.run(generate_voice(script))

    img_path = generate_ai_visual(strong_title)

    audio = AudioFileClip("voice.mp3")
    duration = audio.duration + 0.7

    if img_path:
        raw_clip = ImageClip(img_path).set_duration(duration)
        # Slow dramatic zoom
        animated_bg = raw_clip.resize(lambda t: 1 + 0.045 * t).set_position("center")
        background = CompositeVideoClip([animated_bg], size=(1080, 1920)).set_duration(duration)
    else:
        background = ColorClip(size=(1080, 1920), color=(8, 8, 20)).set_duration(duration)

    # Title text
    text_clip = TextClip(
        strong_title,
        fontsize=52,
        color="white",
        font="Liberation-Sans-Bold",
        method="caption",
        size=(920, None),
        align="center",
        stroke_color="black",
        stroke_width=2
    ).set_position(("center", 0.32)).set_duration(duration)

    final = CompositeVideoClip([background, text_clip]).set_audio(audio)

    output = "short.mp4"
    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4
    )

    background.close()
    audio.close()
    return output


# ====================== UPLOAD ======================
def upload_video(youtube, video_file, title, hashtags, category_id):
    print("Uploading to YouTube...")

    hashtag_str = " ".join(hashtags)
    full_title = f"{title} {hashtag_str}"
    if len(full_title) > 100:
        full_title = full_title[:97] + "..."

    body = {
        "snippet": {
            "title": full_title,
            "description": f"{title}\n\n{hashtag_str}\n\n#shorts #facts",
            "tags": [h.strip("#") for h in hashtags] + ["shorts", "facts"],
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

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except Exception as e:
            retries += 1
            if retries > 5:
                raise Exception(f"Upload failed: {e}")
            sleep_time = 2 ** retries
            print(f"Retrying in {sleep_time}s...")
            time.sleep(sleep_time)

    print(f"Upload complete! Video ID: {response['id']}")
    return response["id"]


# ====================== MAIN ======================
if __name__ == "__main__":
    try:
        youtube = get_youtube_service()
        strong_title, original_topic, hashtags, category_id = get_trending_data(youtube)
        
        video_path = generate_short(strong_title, original_topic)
        upload_video(youtube, video_path, strong_title, hashtags, category_id)
        
        print("Success!")
    except Exception as e:
        print(f"Critical Error: {e}")
        exit(1)
