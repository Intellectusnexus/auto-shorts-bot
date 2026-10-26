import os
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

def download_trending_short():
    # Clean up old files from previous runs
    for f in os.listdir("."):
        if f.startswith("downloaded_short"):
            os.remove(f)

    # Search top 15 results to guarantee we find one under 90 seconds
    search_query = "ytsearch15:movie recap #shorts"
    
    download_cmd = [
        "yt-dlp",
        "--match-filter", "duration < 90",
        "--max-downloads", "1",
        "--merge-output-format", "mp4",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "-o", "downloaded_short.%(ext)s",
        search_query
    ]
    subprocess.run(download_cmd, check=True)

    # Dynamically find the file yt-dlp just created
    downloaded_files = [f for f in os.listdir(".") if f.startswith("downloaded_short")]
    if not downloaded_files:
        raise FileNotFoundError("[!] yt-dlp failed to find any shorts under 90 seconds.")
        
    return downloaded_files[0]

def process_video(input_file):
    output_file = "final_short.mp4"
    if os.path.exists(output_file):
        os.remove(output_file)
        
    # Apply high brightness, contrast, saturation filters and ensure 9:16 vertical scaling
    filter_string = "eq=brightness=0.08:contrast=1.35:saturation=1.5,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
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

def upload_video(youtube, video_file):
    title = "Best Movie Recap Moment #shorts #trending"
    hashtags = ["#trending", "#viral", "#shorts", "#movierecap"]
    full_title = f"{title} {' '.join(hashtags)}"[:97] + "..."
    
    body = {
        "snippet": {
            "title": full_title, 
            "description": f"Top trending movie moment recap.\n\n{' '.join(hashtags)}", 
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
    return response["id"]

if __name__ == "__main__":
    youtube = get_youtube_service()
    print("Downloading trending vertical movie short...")
    raw_video = download_trending_short()
    print("Processing and enhancing video filters...")
    final_video = process_video(raw_video)
    print("Uploading to YouTube...")
    upload_video(youtube, final_video)
    print("Done!")
    
