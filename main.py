import os
import subprocess
import re
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ.get("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("YT_CLIENT_ID"),
        client_secret=os.environ.get("YT_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
    )
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def fetch_trending_topic_and_download(youtube):
    for f in os.listdir("."):
        if f.startswith("raw_video"):
            os.remove(f)

    print("Searching YouTube API for the highest hit shorts from the past 7 days...")
    
    seven_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)).isoformat().replace("+00:00", "Z")
    
    request = youtube.search().list(
        part="snippet",
        q="movie recap #shorts",
        type="video",
        videoDuration="short",
        publishedAfter=seven_days_ago,
        order="viewCount",
        maxResults=10
    )
    response = request.execute()
    
    if not response.get("items"):
        raise ValueError("No trending videos found in the search scope.")
        
    top_video = response["items"][0]
    video_id = top_video["id"]["videoId"]
    original_title = top_video["snippet"]["title"]
    target_url = f"https://www.youtube.com/watch?v={video_id}"
    
    print(f"Target Acquired: {original_title} ({target_url})")
    
    # Using 'ios' player client to bypass YouTube bot detection on cloud servers
    download_cmd = [
        "yt-dlp",
        "--extractor-args", "youtube:player_client=ios",
        "--max-downloads", "1",
        "--merge-output-format", "mp4",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "-o", "raw_video.%(ext)s",
        target_url
    ]
    subprocess.run(download_cmd, check=True)
    
    downloaded_files = [f for f in os.listdir(".") if f.startswith("raw_video.")]
    return downloaded_files[0], original_title

def process_remix_clip(input_file, title):
    output_file = "final_remix.mp4"
    if os.path.exists(output_file):
        os.remove(output_file)
        
    clean_text = re.sub(r'[^\w\s]', '', title)[:40]
    
    print("Extracting clip and applying high brightness, contrast, and saturation filters...")
    
    filter_string = (
        "eq=brightness=0.08:contrast=1.3:saturation=1.4,"
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"drawtext=text='{clean_text}':fontcolor=white:fontsize=72:borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.15"
    )
    
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-ss", "00:00:05",
        "-t", "12",
        "-i", input_file,
        "-vf", filter_string,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "192k",
        output_file
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    return output_file

def upload_to_youtube(youtube, video_file, original_title):
    clean_title = re.sub(r'[^\w\s]', '', original_title)
    words = clean_title.split()
    keywords = " ".join(words[:5])
    
    hashtags = ["#shorts", "#trending", "#viral"]
    final_title = f"{keywords} {' '.join(hashtags)}"
    
    if len(final_title) > 100:
        final_title = final_title[:95] + "..."
        
    body = {
        "snippet": {
            "title": final_title, 
            "description": f"Trending topic highlight.\n\n{' '.join(hashtags)}", 
            "tags": [h.strip("#") for h in hashtags], 
            "categoryId": "24"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_file, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
    return response.get("id")

if __name__ == "__main__":
    youtube = get_youtube_service()
    raw_video, orig_title = fetch_trending_topic_and_download(youtube)
    final_video = process_remix_clip(raw_video, orig_title)
    print("Uploading remixed clip to YouTube...")
    upload_to_youtube(youtube, final_video, orig_title)
    print("Workflow Complete.")
    
